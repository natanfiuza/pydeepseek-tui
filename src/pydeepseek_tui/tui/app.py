import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input
from textual.containers import Vertical
from pydeepseek_tui.agent.activity import SessionActivityLogger
from pydeepseek_tui.config.debug_logger import DebugLogger
from pydeepseek_tui.providers.factory import ProviderFactory
from pydeepseek_tui.agent import Agent, AgentMode
from pydeepseek_tui.agent.session import save_session
from pydeepseek_tui.tools.registry import get_core_registry
from pydeepseek_tui.tui.widgets.chat import ChatLog
from pydeepseek_tui.tui.widgets.statusbar import StatusBar
from pydeepseek_tui.tui.widgets.session_info import SessionInfo

MODE_CYCLE = [AgentMode.PLAN, AgentMode.AGENT, AgentMode.YOLO]


class PyDeepSeekApp(App[None]):
    """Interface Grafica no Terminal para o PyDeepSeek."""

    CSS = """
    SessionInfo {
        dock: top;
        height: 1;
        background: $surface;
        color: $text;
        text-align: right;
        padding: 0 1;
    }
    Input {
        dock: bottom;
        margin: 1 2;
    }
    ChatLog {
        margin: 1 2;
        height: 1fr;
    }
    StatusBar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("q", "save_and_quit", "Sair"),
        ("c", "clear", "Limpar ecra"),
        ("m", "cycle_mode", "Alternar modo"),
        ("p", "cycle_provider", "Alternar provider"),
    ]

    def __init__(self) -> None:
        super().__init__()
        activity = SessionActivityLogger.get_instance()
        DebugLogger.init(activity.session_id)

        provider = ProviderFactory.get_provider()
        registry = get_core_registry()
        self.mode: AgentMode = AgentMode.AGENT
        self.agent = Agent(
            provider=provider,
            registry=registry,
            mode=self.mode,
            on_confirm=self._tui_confirm,
        )
        self._session_id = activity.session_id

    @property
    def mode_label(self) -> str:
        labels = {
            AgentMode.PLAN: "Plano",
            AgentMode.AGENT: "Agente",
            AgentMode.YOLO: "YOLO",
        }
        return labels.get(self.mode, self.mode.value)

    def _update_status(self) -> None:
        bar = self.query_one(StatusBar)
        bar.update_status(
            mode=self.mode_label,
            provider=self.agent.provider.__class__.__name__,
            model=getattr(self.agent.provider, "model", "N/A"),
        )
        activity = SessionActivityLogger.get_instance()
        activity.update_metadata(
            provider=self.agent.provider.__class__.__name__.replace(
                "Provider", ""
            ).lower(),
            model=getattr(self.agent.provider, "model", ""),
            mode=self.mode.value,
        )

    def _refresh_session_stats(self) -> None:
        activity = SessionActivityLogger.get_instance()
        stats = activity.get_stats()
        info_widget = self.query_one(SessionInfo)
        info_widget.update_stats(stats)

    async def _tui_confirm(self, tool_name: str, args: str) -> bool:
        from pydeepseek_tui.tui.widgets.confirm_screen import ConfirmScreen

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        screen = ConfirmScreen(tool_name, args, future)
        await self.push_screen(screen)
        self.refresh()

        result = await future

        if result == "all":
            self.mode = AgentMode.YOLO
            self.agent.mode = self.mode
            self.query_one(ChatLog).write_system(
                "Modo alterado para YOLO: todas as operacoes serao executadas."
            )
            self._update_status()
            return True
        return bool(result)

    def action_save_and_quit(self) -> None:
        activity = SessionActivityLogger.get_instance()
        activity.update_metadata(
            provider=self.agent.provider.__class__.__name__.replace(
                "Provider", ""
            ).lower(),
            model=getattr(self.agent.provider, "model", ""),
            mode=self.mode.value,
        )
        activity.set_saved()
        save_session(
            self.agent.conversation_history,
            provider=self.agent.provider.__class__.__name__.replace(
                "Provider", ""
            ).lower(),
            model=getattr(self.agent.provider, "model", ""),
            mode=self.mode.value,
            session_id=self._session_id,
        )
        self.exit()

    def action_cycle_mode(self) -> None:
        current_idx = MODE_CYCLE.index(self.mode)
        self.mode = MODE_CYCLE[(current_idx + 1) % len(MODE_CYCLE)]
        self.agent.mode = self.mode
        self.query_one(ChatLog).write_system(f"Modo alterado para: {self.mode_label}")
        self._update_status()

    def action_cycle_provider(self) -> None:
        log = self.query_one(ChatLog)
        log.write_system("Alternar provider requer reinicio da aplicacao.")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield SessionInfo(id="session-info")
        yield Vertical(
            ChatLog(id="chat-log", wrap=True),
            Input(
                placeholder="Faz uma pergunta a IA...",
                id="prompt-input",
            ),
        )
        yield StatusBar()
        yield Footer()

    async def on_mount(self) -> None:
        self._update_status()
        self._refresh_session_stats()
        self.set_interval(5.0, self._refresh_session_stats)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return

        log = self.query_one(ChatLog)
        input_widget = self.query_one(Input)

        user_text = event.value
        input_widget.value = ""
        input_widget.disabled = True

        log.write_user_message(user_text)
        log.write_system("a pensar...")

        try:
            response_chunks: list[str] = []
            async for chunk in self.agent.chat_stream(user_text):
                response_chunks.append(chunk)

            # Escreve resposta acumulada para evitar quebras de linha por chunk
            full_response = "".join(response_chunks)
            if full_response.strip():
                log.write_stream(full_response)
                debug = DebugLogger.get_instance()
                if debug:
                    debug.log_output(full_response)

        except Exception as e:
            log.write_error(str(e))
            debug = DebugLogger.get_instance()
            if debug:
                debug.log_error(str(e))
        finally:
            input_widget.disabled = False
            input_widget.focus()
            self._refresh_session_stats()

    def action_clear(self) -> None:
        self.query_one(ChatLog).clear()
