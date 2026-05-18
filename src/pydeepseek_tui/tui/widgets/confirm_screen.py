import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen):
    """Modal de confirmacao para ferramentas destrutivas."""

    BINDINGS = [
        ("s", "yes", "(S)im"),
        ("t", "all", "(T)odos"),
        ("n", "no", "(N)ao"),
        ("escape", "no", "Fechar"),
    ]

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #dialog {
        width: 64;
        background: $panel;
        border: solid $primary;
        padding: 1 2;
    }
    #btns {
        align: center middle;
    }
    #btn-yes {
        background: green;
        color: $text;
    }
    """

    def __init__(
        self, tool_name: str, args: str, future: asyncio.Future
    ) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.args = args
        self._future = future

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(
                f"O agente quer executar: {self.tool_name}"
            )
            yield Static(f"Args: {self.args[:200]}")
            yield Static("Permite executar esta operacao?")
            with Horizontal(id="btns"):
                yield Button("(S)im", variant="primary", id="btn-yes")
                yield Button("Sim para (T)odos", variant="warning", id="btn-all")
                yield Button("(N)ao", variant="error", id="btn-no")

    def action_yes(self) -> None:
        self._finish(True)

    def action_all(self) -> None:
        self._finish("all")

    def action_no(self) -> None:
        self._finish(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self._finish(True)
        elif event.button.id == "btn-all":
            self._finish("all")
        elif event.button.id == "btn-no":
            self._finish(False)

    def _finish(self, result) -> None:
        if not self._future.done():
            self._future.set_result(result)
        self.dismiss()
