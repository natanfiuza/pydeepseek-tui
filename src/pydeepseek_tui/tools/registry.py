from typing import Dict, Any, List
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.file_reader import FileReaderTool
from pydeepseek_tui.tools.web_search import WebSearchTool
from pydeepseek_tui.tools.fetch_url import FetchUrlTool
from pydeepseek_tui.tools.write_file import WriteFileTool
from pydeepseek_tui.tools.shell import ShellTool
from pydeepseek_tui.tools.list_dir import ListDirTool
from pydeepseek_tui.tools.search_files import SearchFilesTool
from pydeepseek_tui.tools.git_tool import GitTool


class ToolRegistry:
    """
    Gerenciador centralizado de ferramentas do agente.
    Permite registrar, recuperar e formatar as ferramentas para a API.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registra uma nova ferramenta no gerenciador."""
        if tool.name in self._tools:
            raise ValueError(f"A ferramenta '{tool.name}' já está registrada.")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """Recupera uma ferramenta pelo nome."""
        if name not in self._tools:
            raise KeyError(f"Ferramenta '{name}' não encontrada no registro.")
        return self._tools[name]

    def get_api_schema(self) -> List[Dict[str, Any]]:
        schemas = []
        for tool in self._tools.values():
            params = tool.parameters.copy()
            self._sanitize_params(params)
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": params,
                    },
                }
            )
        return schemas

    @staticmethod
    def _sanitize_params(params: Dict[str, Any]) -> None:
        if "required" in params and not params["required"]:
            del params["required"]
        for prop in params.get("properties", {}).values():
            prop.pop("default", None)


def get_core_registry() -> ToolRegistry:
    """Inicializa o registro e cadastra todas as ferramentas padrao do sistema."""
    registry = ToolRegistry()
    registry.register(FileReaderTool())
    registry.register(WebSearchTool())
    registry.register(FetchUrlTool())
    registry.register(WriteFileTool())
    registry.register(ShellTool())
    registry.register(ListDirTool())
    registry.register(SearchFilesTool())
    registry.register(GitTool())
    return registry
