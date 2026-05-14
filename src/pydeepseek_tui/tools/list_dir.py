"""
tools/list_dir.py — Lista diretórios com árvore visual e metadados.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

_MAX_ENTRIES = 500
_DEFAULT_IGNORE = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    "*.egg-info", ".DS_Store",
}

class ListDirTool(BaseTool):
    name = "list_dir"
    description = (
        "Lista o conteúdo de um diretório em formato de árvore. "
        "Mostra arquivos, subdiretórios, tamanhos e permissões. "
        "Use para explorar a estrutura do projeto antes de ler arquivos específicos."
    )
    category = ToolCategory.FILESYSTEM
    is_destructive = False
    parameters = [
        ToolParameter("path", "string", "Caminho do diretório a listar. Default: diretório atual.", required=False, default="."),
        ToolParameter("depth", "integer", "Profundidade máxima da árvore. Default: 3.", required=False, default=3),
        ToolParameter("show_hidden", "boolean", "Se True, exibe arquivos ocultos (iniciados com '.'). Default: False.", required=False, default=False),
        ToolParameter("show_sizes", "boolean", "Se True, exibe tamanho dos arquivos. Default: True.", required=False, default=True),
    ]

    async def execute(self, path: str = ".", depth: int = 3, show_hidden: bool = False, show_sizes: bool = True, **kwargs: Any) -> ToolResult:
        dir_path = Path(path).expanduser().resolve()
        if not dir_path.exists():
            return ToolResult.error(error=f"Diretório não encontrado: {path}")
        if not dir_path.is_dir():
            return ToolResult.error(error=f"'{path}' não é um diretório. Use 'read_file' para arquivos.")

        lines: list[str] = [f"📁 {dir_path}"]
        total_files = total_dirs = total_size = 0
        entry_count = 0

        def _walk(current: Path, prefix: str, current_depth: int) -> None:
            nonlocal total_files, total_dirs, total_size, entry_count
            if current_depth > depth or entry_count >= _MAX_ENTRIES:
                return
            try:
                entries = sorted(current.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            except PermissionError:
                lines.append(f"{prefix}└── [permissão negada]")
                return

            visible = [e for e in entries if (show_hidden or not e.name.startswith(".")) and e.name not in _DEFAULT_IGNORE]
            for i, entry in enumerate(visible):
                if entry_count >= _MAX_ENTRIES:
                    lines.append(f"{prefix}└── ... (limite de {_MAX_ENTRIES} entradas atingido)")
                    break
                is_last = i == len(visible) - 1
                connector = "└── " if is_last else "├── "
                extension = "    " if is_last else "│   "
                entry_count += 1

                if entry.is_symlink():
                    target = entry.resolve()
                    lines.append(f"{prefix}{connector}🔗 {entry.name} → {target}")
                elif entry.is_dir():
                    total_dirs += 1
                    lines.append(f"{prefix}{connector}📁 {entry.name}/")
                    _walk(entry, prefix + extension, current_depth + 1)
                else:
                    total_files += 1
                    size = entry.stat().st_size if entry.exists() else 0
                    total_size += size
                    size_str = f"  [{_fmt(size)}]" if show_sizes else ""
                    lines.append(f"{prefix}{connector}📄 {entry.name}{size_str}")

        _walk(dir_path, "", 1)
        summary = f"\n{total_dirs} diretório(s), {total_files} arquivo(s), {_fmt(total_size)} total"
        return ToolResult.success("\n".join(lines) + summary, path=str(dir_path), total_files=total_files, total_dirs=total_dirs)

def _fmt(size: int) -> str:
    if size < 1024: return f"{size}B"
    if size < 1024**2: return f"{size/1024:.1f}KB"
    return f"{size/1024**2:.1f}MB"
