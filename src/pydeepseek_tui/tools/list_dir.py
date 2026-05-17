import os
from pathlib import Path
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.sandbox import is_path_allowed


class ListDirTool(BaseTool):

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return (
            "Lista o conteudo de um diretorio com suporte a filtro glob "
            "e profundidade maxima. Util para explorar a estrutura de "
            "projetos e encontrar ficheiros."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho do diretorio a listar. Default: diretorio atual.",
                },
                "pattern": {
                    "type": "string",
                    "description": "Padrao glob para filtrar ficheiros (ex: *.py, **/*.md). Default: *.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Profundidade maxima (default 2, max 5).",
                },
            },
        }

    def _build_glob(self, base: Path, pattern: str, max_depth: int) -> str:
        depth_prefix = "/".join(["*"] * max_depth)
        return str(base / depth_prefix / pattern)

    async def execute(self, **kwargs: Any) -> str:
        path_str = kwargs.get("path") or os.getcwd()
        pattern = kwargs.get("pattern") or "*"
        max_depth = min(kwargs.get("max_depth", 2), 5)

        if not is_path_allowed(str(path_str)):
            return (
                f"Erro de seguranca: O caminho '{path_str}' esta fora "
                "do diretorio de trabalho."
            )

        try:
            base = Path(path_str).resolve()
            if not base.exists():
                return f"Erro: O diretorio '{path_str}' nao existe."
            if not base.is_dir():
                return f"Erro: '{path_str}' nao e um diretorio."

            # Gera globs para cada nivel de profundidade
            results: list[str] = []
            for depth in range(1, max_depth + 1):
                glob_pattern = str(base / "/".join(["*"] * depth) / pattern)
                matches = sorted(base.glob(glob_pattern))
                for m in matches:
                    try:
                        rel = m.relative_to(base)
                    except ValueError:
                        rel = m
                    if m not in [r["path"] for r in results if isinstance(r, dict)]:  # type: ignore[operator]
                        pass
                for m in matches:
                    try:
                        rel = str(m.relative_to(base))
                    except ValueError:
                        rel = str(m)
                    tipo = "D" if m.is_dir() else "F"
                    try:
                        size = m.stat().st_size if m.is_file() else 0
                    except OSError:
                        size = 0
                    if tipo == "F":
                        results.append(f"  [{tipo}] {rel} ({self._fmt_size(size)})")
                    else:
                        results.append(f"  [{tipo}] {rel}/")

            if not results:
                return f"Diretorio '{path_str}' vazio ou nenhum match para '{pattern}'."

            header = f"Conteudo de '{path_str}' (max_depth={max_depth}, pattern='{pattern}'):\n"
            # Remove duplicados preservando ordem
            seen = set()
            unique = []
            for r in results:
                if r not in seen:
                    seen.add(r)
                    unique.append(r)
            return header + "\n".join(unique[:200])

        except Exception as e:
            return f"Erro ao listar diretorio: {str(e)}"

    @staticmethod
    def _fmt_size(size: int) -> str:
        for unit in ("B", "KB", "MB"):
            if size < 1024:
                return f"{size}{unit}"
            size //= 1024
        return f"{size}GB"
