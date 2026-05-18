from typing import Any, Dict

from rich.style import Style
from rich.text import Text
from textual.widgets import Static


class SessionInfo(Static):
    """Widget que mostra estatisticas da sessao (tempo, tokens, custo)."""

    def update_stats(self, stats: Dict[str, Any]) -> None:
        elapsed = stats.get("elapsed_seconds", 0)
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            time_str = f"{hours}h{minutes:02d}m{seconds:02d}s"
        elif minutes > 0:
            time_str = f"{minutes}m{seconds:02d}s"
        else:
            time_str = f"{seconds}s"

        tokens = stats.get("total_tokens", 0)
        cost = stats.get("total_cost", 0.0)

        text = Text()
        text.append(" Sessao: ", Style(dim=True))
        text.append(time_str, Style(bold=True))
        text.append(" | ", Style(dim=True))
        text.append("Tokens: ", Style(dim=True))
        text.append(f"{tokens:,}", Style(bold=True))
        text.append(" | ", Style(dim=True))
        text.append("Custo: ", Style(dim=True))
        text.append(f"${cost:.6f}", Style(bold=True))
        text.append(" ")

        self.update(text)
