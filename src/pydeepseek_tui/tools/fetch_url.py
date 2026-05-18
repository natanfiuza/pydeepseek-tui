import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool


class FetchUrlTool(BaseTool):
    """
    Ferramenta para fazer download e extrair texto limpo de paginas web.
    """

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return (
            "Acessa uma URL e extrai o texto principal da pagina. "
            "Util para ler artigos, documentacoes ou o conteudo de links "
            "encontrados em pesquisas na web."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "A URL completa (http/https) da pagina a ser lida.",
                }
            },
            "required": ["url"],
        }

    async def _fetch(self, url: str) -> str:
        """Tenta obter o conteudo da URL com retry em caso de falha."""
        last_error = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(
                    timeout=10.0, follow_redirects=True
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                return response.text
            except httpx.HTTPError as e:
                last_error = e
                if attempt == 0:
                    await asyncio.sleep(2)
        raise last_error  # type: ignore[misc]

    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url")
        if not url:
            return "Erro: A URL nao foi fornecida."

        try:
            html = await self._fetch(url)
        except httpx.HTTPError as e:
            return f"Erro de rede ao tentar acessar a URL: {str(e)}"
        except Exception as e:
            return f"Erro inesperado ao processar a pagina: {str(e)}"

        try:
            soup = BeautifulSoup(html, "html.parser")

            for element in soup(
                ["script", "style", "header", "footer", "nav", "aside"]
            ):
                element.extract()

            text = soup.get_text(separator="\n")

            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)

            return f"Conteudo extraido de {url}:\n\n{clean_text[:8000]}"

        except Exception as e:
            return f"Erro inesperado ao processar a pagina: {str(e)}"
