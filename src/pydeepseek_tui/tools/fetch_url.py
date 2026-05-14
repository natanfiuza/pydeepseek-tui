"""tools/fetch_url.py -- Busca conteudo de URLs HTTP e converte para texto."""
from __future__ import annotations
from typing import Any
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

_MAX_CONTENT = 50_000
_TIMEOUT = 15

class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = (
        "Faz uma requisicao HTTP GET para uma URL e retorna o conteudo como texto. "
        "Para paginas HTML, converte para markdown legivel. "
        "Use para ler documentacao online, APIs REST, arquivos raw do GitHub, etc."
    )
    category = ToolCategory.NETWORK
    is_destructive = False
    parameters = [
        ToolParameter("url", "string", "URL a buscar (http/https).", required=True),
        ToolParameter("as_markdown", "boolean", "Se True (padrao), converte HTML para markdown.", required=False, default=True),
        ToolParameter("timeout", "integer", f"Timeout em segundos. Default: {_TIMEOUT}.", required=False, default=_TIMEOUT),
    ]

    async def execute(self, url: str, as_markdown: bool = True,
                      timeout: int = _TIMEOUT, **kw: Any) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            return ToolResult.error(error=f"URL invalida: {url!r}. Deve comecar com http:// ou https://")

        try:
            import httpx
        except ImportError:
            return ToolResult.error(error="httpx nao instalado.", output="Execute: pip install httpx")

        try:
            async with httpx.AsyncClient(timeout=float(timeout or _TIMEOUT),
                                         follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "pydeepseek-tui/1.0"})
                resp.raise_for_status()
        except httpx.TimeoutException:
            return ToolResult.timeout(timeout or _TIMEOUT)
        except httpx.HTTPStatusError as exc:
            return ToolResult.error(error=f"HTTP {exc.response.status_code}: {url}")
        except Exception as exc:
            return ToolResult.error(error=f"Erro ao buscar URL: {exc}")

        content_type = resp.headers.get("content-type", "")
        raw = resp.text

        if as_markdown and "text/html" in content_type:
            raw = _html_to_text(raw)

        if len(raw) > _MAX_CONTENT:
            raw = raw[:_MAX_CONTENT] + f"\n\n... [truncado — {len(raw)} chars total]"

        header = f"URL: {url}\nStatus: {resp.status_code}\nContent-Type: {content_type}\n\n"
        return ToolResult.success(header + raw, url=url, status_code=resp.status_code,
                                  content_length=len(raw))

def _html_to_text(html: str) -> str:
    try:
        from markdownify import markdownify
        return markdownify(html, heading_style="ATX", strip=["script", "style"])
    except ImportError:
        pass
    import re
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.S|re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    import html as html_mod
    text = html_mod.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
