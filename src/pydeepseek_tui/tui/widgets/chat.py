import re
from rich.style import Style
from rich.text import Text
from textual.widgets import RichLog

_RE_MARKUP = re.compile(r"\[/?[a-z#][a-z0-9_ -]*\]", re.IGNORECASE)


def _safe_markup(text: str) -> Text:
    """Converte texto com markup Rich para Text, mantendo texto puro se nao houver tags."""
    if _RE_MARKUP.search(text):
        try:
            return Text.from_markup(text)
        except Exception:
            pass
    return Text(text)


class ChatLog(RichLog):

    def write_user_message(self, text: str) -> None:
        msg = Text("\n")
        msg.append("Voce: ", Style(bold=True, color="green"))
        msg.append(text)
        self.write(msg)

    def write_assistant_message(self, text: str) -> None:
        msg = Text()
        msg.append("Assistente: ", Style(bold=True, color="magenta"))
        msg.append(text)
        msg.append("\n")
        self.write(msg)

    def write_tool_execution(self, tool_name: str) -> None:
        msg = Text("\n")
        msg.append(f"Executando {tool_name}...", Style(bold=True, color="yellow"))
        self.write(msg)

    def write_tool_blocked(self, tool_name: str, reason: str) -> None:
        msg = Text("\n")
        msg.append(f"Bloqueado {tool_name}: ", Style(bold=True, color="yellow"))
        msg.append(reason)
        self.write(msg)

    def write_error(self, text: str) -> None:
        msg = Text()
        msg.append("Erro: ", Style(bold=True, color="red"))
        msg.append(text)
        msg.append("\n")
        self.write(msg)

    def write_system(self, text: str) -> None:
        msg = Text("\n")
        msg.append(text, Style(dim=True))
        msg.append("\n")
        self.write(msg)

    def write_stream(self, text: str) -> None:
        self.write(_safe_markup(text))
