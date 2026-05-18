from textual.widgets import Static


class StatusBar(Static):
    """Barra de status mostrando modo, provider e modelo."""

    def update_status(self, mode: str, provider: str, model: str) -> None:
        self.update(f" Modo: {mode} | Provider: {provider} | Modelo: {model} ")
