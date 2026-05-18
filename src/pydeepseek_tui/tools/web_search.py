from typing import Any, Dict
from duckduckgo_search import DDGS
from pydeepseek_tui.tools.base import BaseTool


class WebSearchTool(BaseTool):
    """
    Ferramenta para pesquisar informações atualizadas na internet.
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Realiza uma pesquisa na internet e devolve os resultados mais relevantes. "
            "Usa esta ferramenta quando precisares de informações recentes, notícias ou dados "
            "que não estão no teu conhecimento base."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Os termos de pesquisa a serem procurados na web.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "O número máximo de resultados a devolver (o padrão é 5).",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Executa a pesquisa na web e formata os resultados."""
        query = kwargs.get("query")
        max_results = kwargs.get("max_results", 5)

        if not query:
            return "Erro: O termo de pesquisa (query) não foi fornecido."

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return "Nenhum resultado encontrado para a tua pesquisa."

            formatted_results = "\n\n".join(
                f"Título: {res.get('title')}\nURL: {res.get('href')}\nResumo: {res.get('body')}"
                for res in results
            )
            return f"Resultados da pesquisa para '{query}':\n\n{formatted_results}"
        except Exception as e:
            return f"Erro ao tentar realizar a pesquisa na web: {str(e)}"
