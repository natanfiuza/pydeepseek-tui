"""
tui/app.py
==========

DeepSeekApp -- Aplicacao Textual principal do pydeepseek-tui.

Estrutura da tela:
  ┌─────────────────────────────────────────┐
  │  Header: titulo + provider + modo       │
  ├───────────────────┬─────────────────────┤
  │                   │  ThinkingPanel      │
  │   ChatPanel       │  (colapsavel)       │
  │   (historico +    ├─────────────────────┤
  │    streaming)     │  ToolsPanel         │
  │                   │  (ultima tool)      │
  ├───────────────────┴─────────────────────┤
  │  InputBar (textarea + botoes)           │
  ├─────────────────────────────────────────┤
  │  Footer: atalhos de teclado             │
  └─────────────────────────────────────────┘

Atalhos de teclado:
  Ctrl+S   : Enviar mensagem
  Ctrl+L   : Limpar historico
  Ctrl+P   : Alternar provider
  Ctrl+M   : Alternar modo (plan/agent/yolo)
  Ctrl+T   : Alternar painel de thinking
  Ctrl+K   : Abrir sessoes salvas
  Escape   : Cancelar geracao atual
  F1       : Ajuda
"""

from __future__ import annotations

import asyncio
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Footer, Header

from pydeepseek_tui.agent.loop import AgentLoop, AgentResponse, ToolCallEvent
from pydeepseek_tui.agent.session import SessionManager
from pydeepseek_tui.config.settings import AgentMode, Provider, get_settings
from pydeepseek_tui.providers import ProviderFactory
from pydeepseek_tui.providers.base import StreamChunk
from pydeepseek_tui.tools.base import ToolResult
from pydeepseek_tui.tools.registry import ToolRegistry
from pydeepseek_tui.tui.panels.chat import ChatPanel
from pydeepseek_tui.tui.panels.input_bar import InputBar
from pydeepseek_tui.tui.panels.thinking import ThinkingPanel
from pydeepseek_tui.tui.panels.tools import ToolsPanel
from pydeepseek_tui.tui.modals.confirm import ConfirmModal
from pydeepseek_tui.tui.modals.provider_select import ProviderSelectModal
from pydeepseek_tui.tui.modals.session_browser import SessionBrowserModal


class DeepSeekApp(App):
    """
    Aplicacao TUI principal do pydeepseek-tui.

    Orquestra todos os paineis, modais e o AgentLoop.
    Gerencia estado global: provider ativo, modo, sessao atual.
    """

    TITLE = "pydeepseek-tui"
    CSS_PATH = "styles/main.tcss"

    BINDINGS = [
        Binding("ctrl+s",     "send_message",      "Enviar",        show=True),
        Binding("ctrl+l",     "clear_history",     "Limpar",        show=True),
        Binding("ctrl+p",     "select_provider",   "Provider",      show=True),
        Binding("ctrl+m",     "toggle_mode",       "Modo",          show=True),
        Binding("ctrl+t",     "toggle_thinking",   "Thinking",      show=False),
        Binding("ctrl+k",     "open_sessions",     "Sessoes",       show=True),
        Binding("escape",     "cancel_generation", "Cancelar",      show=False),
        Binding("f1",         "show_help",         "Ajuda",         show=True),
        Binding("ctrl+q",     "quit",              "Sair",          show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._settings = get_settings()
        self._agent_mode = self._settings.agent_mode
        self._session_manager = SessionManager()
        self._current_session_id: Optional[str] = None
        self._is_generating = False
        self._generation_task: Optional[asyncio.Task] = None

        # Inicializa provider e agent loop
        self._provider = ProviderFactory.from_settings(self._settings)
        self._registry = ToolRegistry(agent_mode=self._agent_mode)
        self._registry.register_defaults()
        self._registry.confirmation_callback = self._confirm_tool_execution
        self._agent = self._build_agent()

    # ------------------------------------------------------------------
    # Composicao da UI
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatPanel(id="chat-panel")
        yield ThinkingPanel(id="thinking-panel")
        yield ToolsPanel(id="tools-panel")
        yield InputBar(id="input-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Inicializa a UI apos montagem."""
        self._update_header()
        self.query_one(InputBar).focus()

        # Exibe mensagem de boas-vindas
        cfg = self._settings
        meta = ProviderFactory.get_metadata(cfg.provider)
        self.query_one(ChatPanel).add_system_message(
            f"Bem-vindo ao pydeepseek-tui!
"
            f"Provider: {meta['icon']} {meta['name']} | "
            f"Modelo: {self._provider.model} | "
            f"Modo: {self._agent_mode.value.upper()}

"
            f"Digite sua mensagem e pressione Ctrl+S para enviar. "
            f"Use F1 para ver todos os atalhos."
        )

    # ------------------------------------------------------------------
    # Envio de mensagem
    # ------------------------------------------------------------------

    @on(InputBar.MessageSubmitted)
    async def handle_message_submitted(self, event: InputBar.MessageSubmitted) -> None:
        """Recebe mensagem do InputBar e inicia a geracao."""
        await self._start_generation(event.message)

    async def action_send_message(self) -> None:
        """Acao Ctrl+S: envia a mensagem do InputBar."""
        input_bar = self.query_one(InputBar)
        message = input_bar.get_message()
        if message.strip():
            input_bar.clear()
            await self._start_generation(message)

    async def _start_generation(self, user_message: str) -> None:
        """Inicia a geracao de resposta em background."""
        if self._is_generating:
            self.notify("Aguarde a geracao atual terminar.", severity="warning")
            return

        self._is_generating = True
        chat = self.query_one(ChatPanel)
        chat.add_user_message(user_message)
        chat.start_assistant_message()

        input_bar = self.query_one(InputBar)
        input_bar.set_generating(True)

        # Limpa paineis laterais
        self.query_one(ThinkingPanel).clear()
        self.query_one(ToolsPanel).clear()

        self._generation_task = asyncio.create_task(
            self._run_generation(user_message)
        )

    @work(exclusive=True)
    async def _run_generation(self, user_message: str) -> None:
        """Worker que executa o AgentLoop em background."""
        chat = self.query_one(ChatPanel)
        thinking_panel = self.query_one(ThinkingPanel)
        tools_panel = self.query_one(ToolsPanel)

        try:
            async for chunk in self._agent.stream(user_message):
                if not self._is_generating:
                    break  # Cancelado pelo usuario

                # Texto da resposta
                if chunk.content:
                    self.call_from_thread(chat.append_assistant_chunk, chunk.content)

                # Chain-of-thought
                if chunk.thinking:
                    self.call_from_thread(thinking_panel.append_thinking, chunk.thinking)

                # Chunk final com metricas
                if chunk.is_final and chunk.usage:
                    cost = self._provider.estimate_cost(chunk.usage)
                    self.call_from_thread(
                        chat.finalize_assistant_message,
                        chunk.usage,
                        cost,
                    )

        except asyncio.CancelledError:
            self.call_from_thread(chat.add_system_message, "[Geracao cancelada]")
        except Exception as exc:
            self.call_from_thread(
                chat.add_error_message,
                f"Erro durante geracao: {exc}"
            )
        finally:
            self.call_from_thread(self._finish_generation)

    def _finish_generation(self) -> None:
        """Finaliza o estado de geracao na UI."""
        self._is_generating = False
        self._generation_task = None
        try:
            self.query_one(InputBar).set_generating(False)
            self.query_one(InputBar).focus()
        except NoMatches:
            pass

    # ------------------------------------------------------------------
    # Callbacks do AgentLoop (tools)
    # ------------------------------------------------------------------

    async def _on_tool_call(self, tool_name: str, arguments: dict) -> None:
        """Chamado antes de executar uma tool."""
        self.call_from_thread(
            self.query_one(ToolsPanel).show_tool_executing,
            tool_name,
            arguments,
        )
        self.call_from_thread(
            self.query_one(ChatPanel).add_tool_call_indicator,
            tool_name,
        )

    async def _on_tool_result(self, event: ToolCallEvent) -> None:
        """Chamado apos executar uma tool."""
        self.call_from_thread(
            self.query_one(ToolsPanel).show_tool_result,
            event,
        )

    async def _confirm_tool_execution(self, tool, kwargs: dict) -> bool:
        """
        Exibe modal de confirmacao para tools destrutivas no modo agent.
        Retorna True para confirmar, False para cancelar.
        """
        result = await self.push_screen_wait(
            ConfirmModal(
                tool_name=tool.name,
                tool_description=tool.description,
                arguments=kwargs,
            )
        )
        return bool(result)

    # ------------------------------------------------------------------
    # Acoes de teclado
    # ------------------------------------------------------------------

    async def action_cancel_generation(self) -> None:
        """Escape: cancela a geracao atual."""
        if self._is_generating and self._generation_task:
            self._is_generating = False
            self._generation_task.cancel()
            self.notify("Geracao cancelada.", severity="information")

    async def action_clear_history(self) -> None:
        """Ctrl+L: limpa historico com confirmacao."""
        if not self._agent.get_history():
            self.notify("Historico ja esta vazio.", severity="information")
            return

        confirmed = await self.push_screen_wait(
            ConfirmModal(
                tool_name="Limpar historico",
                tool_description="Esta acao ira remover todas as mensagens da sessao atual.",
                arguments={},
                confirm_label="Limpar",
                danger=True,
            )
        )
        if confirmed:
            self._agent.clear_history()
            self.query_one(ChatPanel).clear()
            self.query_one(ThinkingPanel).clear()
            self.query_one(ToolsPanel).clear()
            self.notify("Historico limpo.", severity="information")

    async def action_select_provider(self) -> None:
        """Ctrl+P: abre modal de selecao de provider."""
        result = await self.push_screen_wait(ProviderSelectModal())
        if result:
            provider_enum, model = result
            await self._switch_provider(provider_enum, model)

    async def action_toggle_mode(self) -> None:
        """Ctrl+M: alterna entre modos plan -> agent -> yolo -> plan."""
        modes = [AgentMode.PLAN, AgentMode.AGENT, AgentMode.YOLO]
        current_idx = modes.index(self._agent_mode)
        next_mode = modes[(current_idx + 1) % len(modes)]
        self._agent_mode = next_mode
        self._registry.agent_mode = next_mode
        self._update_header()
        mode_icons = {AgentMode.PLAN: "📋", AgentMode.AGENT: "🤖", AgentMode.YOLO: "⚡"}
        self.notify(
            f"Modo alterado para {mode_icons[next_mode]} {next_mode.value.upper()}",
            severity="information",
        )

    def action_toggle_thinking(self) -> None:
        """Ctrl+T: mostra/esconde painel de thinking."""
        panel = self.query_one(ThinkingPanel)
        panel.toggle_visible()

    async def action_open_sessions(self) -> None:
        """Ctrl+K: abre navegador de sessoes salvas."""
        result = await self.push_screen_wait(
            SessionBrowserModal(session_manager=self._session_manager)
        )
        if result == "new":
            await self.action_clear_history()
        elif result:
            # Carrega sessao selecionada
            session = self._session_manager.load(result)
            if session:
                self._agent.load_history(session.messages)
                self._current_session_id = session.session_id
                self.query_one(ChatPanel).load_history(session.messages)
                self.notify(f"Sessao '{session.name}' carregada.", severity="success")

    async def action_show_help(self) -> None:
        """F1: exibe painel de ajuda."""
        from pydeepseek_tui.tui.modals.help import HelpModal
        await self.push_screen(HelpModal())

    # ------------------------------------------------------------------
    # Troca de provider
    # ------------------------------------------------------------------

    async def _switch_provider(self, provider: Provider, model: Optional[str]) -> None:
        """Troca o provider e reconstroi o AgentLoop."""
        try:
            self._settings.provider = provider
            if model:
                # Atualiza o modelo nas settings dinamicamente
                model_attr = f"{provider.value}_model"
                if hasattr(self._settings, model_attr):
                    setattr(self._settings, model_attr, model)

            self._provider = ProviderFactory.from_settings(self._settings)
            self._agent = self._build_agent()
            self._update_header()

            meta = ProviderFactory.get_metadata(provider)
            self.notify(
                f"Provider alterado para {meta['icon']} {meta['name']} ({self._provider.model})",
                severity="success",
            )
        except Exception as exc:
            self.notify(f"Erro ao trocar provider: {exc}", severity="error")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_agent(self) -> AgentLoop:
        """Constroi uma nova instancia do AgentLoop com os providers atuais."""
        return AgentLoop(
            provider=self._provider,
            registry=self._registry,
            agent_mode=self._agent_mode,
            on_tool_call=self._on_tool_call,
            on_tool_result=self._on_tool_result,
        )

    def _update_header(self) -> None:
        """Atualiza o subtitulo do Header com provider e modo atuais."""
        meta = ProviderFactory.get_metadata(self._settings.provider)
        mode_icons = {AgentMode.PLAN: "📋", AgentMode.AGENT: "🤖", AgentMode.YOLO: "⚡"}
        icon = mode_icons.get(self._agent_mode, "🤖")
        self.sub_title = (
            f"{meta['icon']} {meta['name']} / {self._provider.model} | "
            f"{icon} {self._agent_mode.value.upper()}"
        )

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def action_quit(self) -> None:
        """Ctrl+Q: salva sessao e sai."""
        history = self._agent.get_history()
        if history:
            self._session_manager.save(
                messages=history,
                session_id=self._current_session_id,
                provider=self._settings.provider.value,
                model=self._provider.model,
            )
        self.exit()
