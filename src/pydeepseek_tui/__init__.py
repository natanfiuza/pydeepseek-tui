"""
pydeepseek-tui
==============

Agente de IA com interface TUI no terminal.
Inspirado no DeepSeek-TUI, construído em Python com Textual.

Autor:  Natan Fiuza <contato@natanfiuza.dev.br>
Licença: MIT
"""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__", "__author__", "__email__"]

try:
    __version__: str = version("pydeepseek-tui")
except PackageNotFoundError:
    # Pacote ainda não instalado (desenvolvimento local)
    __version__ = "0.1.0-dev"

__author__: str = "Natan Fiuza"
__email__: str = "contato@natanfiuza.dev.br"
