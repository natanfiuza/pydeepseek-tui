"""
tools/search_files.py — Busca por conteúdo (grep) e por nome de arquivo.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

_MAX_RESULTS = 100
_MAX_LINE_LEN = 200
_IGNORE_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", "dist", "build"}

class SearchFilesTool(BaseTool):
    name = "search_files"
    description = (
        "Busca por conteúdo dentro de arquivos (como grep) ou por nome de arquivo. "
        "Suporta expressões regulares. "
        "Use para encontrar definições de funções, imports, strings, padrões de código, etc."
    )
    category = ToolCategory.SEARCH
    is_destructive = False
    parameters = [
        ToolParameter("pattern", "string", "Padrão de busca (texto literal ou regex).", required=True),
        ToolParameter("path", "string", "Diretório ou arquivo onde buscar. Default: '.' (projeto inteiro).", required=False, default="."),
        ToolParameter("search_type", "string", "Tipo de busca: 'content' (dentro de arquivos) ou 'filename' (por nome). Default: 'content'.", required=False, default="content", enum=["content", "filename"]),
        ToolParameter("file_pattern", "string", "Filtro de extensão, ex: '*.py', '*.ts'. Default: todos os arquivos.", required=False, default="*"),
        ToolParameter("case_sensitive", "boolean", "Se True, busca com diferenciação de maiúsculas. Default: False.", required=False, default=False),
        ToolParameter("context_lines", "integer", "Linhas de contexto ao redor de cada match (0-5). Default: 1.", required=False, default=1),
    ]

    async def execute(self, pattern: str, path: str = ".", search_type: str = "content",
                      file_pattern: str = "*", case_sensitive: bool = False,
                      context_lines: int = 1, **kwargs: Any) -> ToolResult:
        base = Path(path).expanduser().resolve()
        if not base.exists():
            return ToolResult.error(error=f"Caminho não encontrado: {path}")

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return ToolResult.error(error=f"Padrão regex inválido: {exc}")

        results: list[str] = []
        match_count = 0

        if search_type == "filename":
            for entry in _iter_files(base, file_pattern):
                if regex.search(entry.name):
                    results.append(f"  {entry.relative_to(base)}")
                    match_count += 1
                    if match_count >= _MAX_RESULTS:
                        results.append(f"  ... (limite de {_MAX_RESULTS} resultados)")
                        break
        else:
            for file_path in _iter_files(base, file_pattern):
                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                lines = text.splitlines()
                file_matches: list[str] = []
                for i, line in enumerate(lines):
                    if regex.search(line):
                        ctx_start = max(0, i - context_lines)
                        ctx_end = min(len(lines), i + context_lines + 1)
                        block: list[str] = []
                        for j in range(ctx_start, ctx_end):
                            marker = ">" if j == i else " "
                            ln = lines[j][:_MAX_LINE_LEN]
                            block.append(f"  {marker} {j+1:4d} | {ln}")
                        file_matches.append("\n".join(block))
                        match_count += 1
                        if match_count >= _MAX_RESULTS:
                            break
                if file_matches:
                    rel = file_path.relative_to(base)
                    results.append(f"\n📄 {rel}:")
                    results.extend(file_matches)
                if match_count >= _MAX_RESULTS:
                    results.append(f"\n... (limite de {_MAX_RESULTS} matches atingido)")
                    break

        if not results:
            return ToolResult.success(f"Nenhum resultado encontrado para '{pattern}' em '{path}'.", match_count=0)

        header = f"🔍 {match_count} match(es) para '{pattern}' em '{base}'\n"
        return ToolResult.success(header + "\n".join(results), match_count=match_count, path=str(base))

def _iter_files(base: Path, pattern: str):
    glob = "**/" + pattern if pattern != "*" else "**/*"
    for p in sorted(base.glob(glob)):
        if p.is_file() and not any(part in _IGNORE_DIRS for part in p.parts):
            yield p
