from textual.widgets import Static


class ToolPanel(Static):
    """Painel que mostra a ultima tool executada."""

    def show_tool(self, name: str, result: str) -> None:
        preview = result[:200] + "..." if len(result) > 200 else result
        self.update(f"[bold yellow]Tool: {name}[/bold yellow]\n{preview}")
