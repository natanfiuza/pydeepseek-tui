import os
import re
from pathlib import Path
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.sandbox import is_path_allowed


class SearchFilesTool(BaseTool):

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            "Pesquisa por um padrao regex no conteudo de ficheiros de texto "
            "dentro de um diretorio. Devolve caminho, numero da linha e "
            "conteudo da linha onde o match foi encontrado."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Expressao regular a pesquisar nos ficheiros.",
                },
                "path": {
                    "type": "string",
                    "description": "Diretorio onde pesquisar. Default: diretorio atual.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob para filtrar tipos de ficheiro (ex: *.py, *.md). Default: *.",
                    "default": "*",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Numero maximo de resultados (default 20, max 50).",
                    "default": 20,
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        pattern_str = kwargs.get("pattern")
        path_str = kwargs.get("path") or os.getcwd()
        file_pattern = kwargs.get("file_pattern") or "*"
        max_results = min(kwargs.get("max_results", 20), 50)

        if not pattern_str:
            return "Erro: O padrao de pesquisa (pattern) nao foi fornecido."

        if not is_path_allowed(str(path_str)):
            return (
                f"Erro de seguranca: O caminho '{path_str}' esta fora "
                "do diretorio de trabalho."
            )

        try:
            regex = re.compile(pattern_str)
        except re.error as e:
            return f"Erro: Expressao regular invalida: {str(e)}"

        results: list[str] = []
        base = Path(path_str).resolve()

        if not base.exists():
            return f"Erro: O diretorio '{path_str}' nao existe."

        try:
            for file_path in base.rglob(file_pattern):
                if not file_path.is_file():
                    continue
                if len(results) >= max_results:
                    break

                try:
                    content = file_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        try:
                            rel = str(file_path.relative_to(base))
                        except ValueError:
                            rel = str(file_path)
                        results.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(results) >= max_results:
                            break
        except Exception as e:
            return f"Erro ao percorrer ficheiros: {str(e)}"

        if not results:
            return (
                f"Nenhum resultado para '{pattern_str}' em '{path_str}' "
                f"(filtro: {file_pattern})."
            )

        header = (
            f"Resultados para '{pattern_str}' em '{path_str}' "
            f"(filtro: {file_pattern}):\n\n"
        )
        return header + "\n".join(results)
