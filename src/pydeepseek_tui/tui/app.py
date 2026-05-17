from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input
from textual.containers import Vertical, Horizontal
from pydeepseek_tui.config.debug_logger import DebugLogger
from pydeepseek_tui.providers.factory import ProviderFactory
from pydeepseek_tui.agent import Agent, AgentMode
from pydeepseek_tui.tools.registry import get_core_registry
from pydeepseek_tui.tui.widgets.chat import ChatLog
from pydeepseek_tui.tui.widgets.statusbar import StatusBar

MODE_CYCLE = [AgentMode.PLAN, AgentMode.AGENT, AgentMode.YOLO]


class PyDeepSeekApp(App[None]):
    """Interface Grafica no Terminal para o PyDeepSeek."""

    CSS = """
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
        ("q", "quit", "Sair"),
        ("c", "clear", "Limpar ecra"),
        ("m", "cycle_mode", "Alternar modo"),
        ("p", "cycle_provider", "Alternar provider"),
    ]

    def __init__(self) -> None:
        super().__init__()
        provider = ProviderFactory.get_provider()
        registry = get_core_registry()
        self.mode: AgentMode = AgentMode.AGENT
        self.agent = Agent(
            provider=provider,
            registry=registry,
            mode=self.mode,
            on_confirm=self._tui_confirm,
        )

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

    async def _tui_confirm(self, tool_name: str, args: str) -> bool:
        log = self.query_one(ChatLog)
        log.write_system(
            f"O agente quer executar '{tool_name}' com args: {args}. "
            "Altera o modo para YOLO (m) para executar sem confirmacoes."
        )
        return False

    def action_cycle_mode(self) -> None:
        current_idx = MODE_CYCLE.index(self.mode)
        self.mode = MODE_CYCLE[(current_idx + 1) % len(MODE_CYCLE)]
        self.agent.mode = self.mode
        self.query_one(ChatLog).write_system(
            f"Modo alterado para: {self.mode_label}"
        )
        self._update_status()

    def action_cycle_provider(self) -> None:
        log = self.query_one(ChatLog)
        log.write_system("Alternar provider requer reinicio da aplicacao.")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
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
                debug = DebugLogger.get_instance()
                if debug:
                    debug.log_output(chunk)

            # Escreve resposta acumulada para evitar quebras de linha por chunk
            full_response = "".join(response_chunks)
            if full_response.strip():
                log.write_stream(full_response)

        except Exception as e:
            log.write_error(str(e))
            debug = DebugLogger.get_instance()
            if debug:
                debug.log_error(str(e))
        finally:
            input_widget.disabled = False
            input_widget.focus()

    def action_clear(self) -> None:
        self.query_one(ChatLog).clear()
