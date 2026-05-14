"""
tools/read_file.py
==================

Tool de leitura de arquivos com suporte a:
  - Leitura completa ou parcial (offset + limit de linhas)
  - Detecção automática de encoding
  - Exibição de números de linha
  - Proteção contra arquivos binários e muito grandes
  - Suporte a múltiplos arquivos em uma única chamada
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

# Limite de tamanho para leitura direta (5MB)
_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# Extensões consideradas binárias (não legíveis como texto)
_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pyc", ".pyo", ".class", ".o", ".a",
    ".db", ".sqlite", ".sqlite3",
}

# Encodings a tentar em ordem
_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


class ReadFileTool(BaseTool):
    """
    Lê o conteúdo de um ou mais arquivos do filesystem.

    Não é destrutiva — nunca modifica arquivos.
    Disponível em todos os modos de operação (plan, agent, yolo).
    """

    name = "read_file"
    description = (
        "Lê o conteúdo de um arquivo de texto. "
        "Suporta leitura parcial via offset e limit de linhas. "
        "Use para inspecionar código-fonte, configurações, logs e documentos de texto. "
        "Não funciona com arquivos binários (imagens, executáveis, etc.)."
    )
    category = ToolCategory.FILESYSTEM
    is_destructive = False
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Caminho absoluto ou relativo ao arquivo a ler.",
            required=True,
        ),
        ToolParameter(
            name="offset",
            type="integer",
            description="Número da linha inicial (1-based). Default: 1 (início do arquivo).",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description=(
                "Número máximo de linhas a retornar. "
                "Default: 200. Use -1 para ler o arquivo inteiro."
            ),
            required=False,
            default=200,
        ),
        ToolParameter(
            name="show_line_numbers",
            type="boolean",
            description="Se True, exibe números de linha no output. Default: True.",
            required=False,
            default=True,
        ),
    ]

    async def execute(
        self,
        path: str,
        offset: int = 1,
        limit: int = 200,
        show_line_numbers: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Lê e retorna o conteúdo do arquivo."""
        file_path = Path(path).expanduser().resolve()

        # Verificações de existência e tipo
        if not file_path.exists():
            return ToolResult.error(
                error=f"Arquivo não encontrado: {path}",
                output=f"O caminho '{file_path}' não existe.",
            )

        if file_path.is_dir():
            return ToolResult.error(
                error=f"'{path}' é um diretório, não um arquivo.",
                output="Use a tool 'list_dir' para listar o conteúdo de diretórios.",
            )

        # Verifica extensão binária
        if file_path.suffix.lower() in _BINARY_EXTENSIONS:
            return ToolResult.error(
                error=f"Arquivo binário não suportado: {file_path.suffix}",
                output=(
                    f"O arquivo '{file_path.name}' parece ser binário "
                    f"({file_path.suffix}) e não pode ser lido como texto."
                ),
            )

        # Verifica tamanho
        file_size = file_path.stat().st_size
        if file_size > _MAX_FILE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            return ToolResult.error(
                error=f"Arquivo muito grande: {size_mb:.1f}MB (limite: 5MB)",
                output=(
                    f"Use offset e limit para ler partes específicas do arquivo. "
                    f"Exemplo: offset=1, limit=100 para as primeiras 100 linhas."
                ),
            )

        # Leitura com detecção de encoding
        content, encoding_used = _read_with_encoding(file_path)
        if content is None:
            return ToolResult.error(
                error=f"Não foi possível decodificar '{path}' com nenhum encoding suportado.",
                output="Tente verificar o encoding do arquivo.",
            )

        lines = content.splitlines()
        total_lines = len(lines)

        # Normaliza offset (1-based → 0-based)
        start = max(0, (offset or 1) - 1)
        end = total_lines if limit == -1 else min(total_lines, start + (limit or 200))

        selected_lines = lines[start:end]

        # Formata output
        if show_line_numbers:
            width = len(str(end))
            formatted = "\n".join(
                f"{start + i + 1:>{width}} | {line}"
                for i, line in enumerate(selected_lines)
            )
        else:
            formatted = "\n".join(selected_lines)

        # Monta cabeçalho informativo
        showing = f"linhas {start + 1}–{start + len(selected_lines)}" if selected_lines else "vazio"
        header = (
            f"# Arquivo: {file_path}\n"
            f"# Total de linhas: {total_lines} | Mostrando: {showing} | "
            f"Encoding: {encoding_used} | Tamanho: {_format_size(file_size)}\n"
        )

        # Aviso se há mais linhas disponíveis
        remaining = total_lines - (start + len(selected_lines))
        footer = ""
        if remaining > 0:
            next_offset = start + len(selected_lines) + 1
            footer = (
                f"\n# ... {remaining} linha(s) restante(s). "
                f"Use offset={next_offset} para continuar a leitura."
            )

        output = header + formatted + footer

        return ToolResult.success(
            output,
            file_path=str(file_path),
            total_lines=total_lines,
            lines_shown=len(selected_lines),
            encoding=encoding_used,
            file_size=file_size,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_with_encoding(path: Path) -> tuple[Optional[str], str]:
    """
    Tenta ler o arquivo com múltiplos encodings em sequência.

    Returns:
        Tupla (conteúdo, encoding_usado) ou (None, "") se falhar.
    """
    for encoding in _ENCODINGS:
        try:
            content = path.read_text(encoding=encoding)
            return content, encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None, ""


def _format_size(size_bytes: int) -> str:
    """Formata tamanho em bytes para string legível."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"
