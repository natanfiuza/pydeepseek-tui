"""tools/web_search.py -- Busca na web via DuckDuckGo (sem API key)."""
from __future__ import annotations
from typing import Any
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Busca informacoes na web via DuckDuckGo. Nao requer API key. "
        "Use para pesquisar documentacao, erros, noticias tecnicas e referencias. "
        "Retorna titulos, URLs e trechos relevantes."
    )
    category = ToolCategory.SEARCH
    is_destructive = False
    parameters = [
        ToolParameter("query", "string", "Termos de busca.", required=True),
        ToolParameter("max_results", "integer", "Numero maximo de resultados (1-10). Default: 5.", required=False, default=5),
        ToolParameter("region", "string", "Regiao/idioma. Ex: br-pt, us-en. Default: wt-wt (global).", required=False, default="wt-wt"),
    ]

    async def execute(self, query: str, max_results: int = 5,
                      region: str = "wt-wt", **kw: Any) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return ToolResult.error(
                error="duckduckgo-search nao instalado.",
                output="Execute: pip install duckduckgo-search")

        n = max(1, min(int(max_results or 5), 10))
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, region=region, max_results=n))
        except Exception as exc:
            return ToolResult.error(error=f"Erro na busca: {exc}",
                                    output="Verifique sua conexao com a internet.")

        if not raw:
            return ToolResult.success(f"Nenhum resultado para: {query!r}", match_count=0)

        lines = [f"Resultados para: {query!r}\n"]
        for i, r in enumerate(raw, 1):
            title = r.get("title", "Sem titulo")
            url   = r.get("href", "")
            body  = r.get("body", "")[:300]
            lines.append(f"{i}. {title}\n   URL: {url}\n   {body}\n")

        return ToolResult.success("\n".join(lines), match_count=len(raw), query=query)
