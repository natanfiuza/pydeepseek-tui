"""
tools/write_file.py
===================

Tool de escrita de arquivos com suporte a:
  - Criação de novos arquivos (cria diretórios intermediários automaticamente)
  - Sobrescrita completa de arquivos existentes
  - Inserção de linhas em posição específica
  - Substituição de bloco de linhas (patch cirúrgico)
  - Append ao final do arquivo
  - Backup automático antes de modificar arquivos existentes

É destrutiva — requer confirmação em modo 'agent' e é bloqueada em modo 'plan'.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

# Diretório de backups (relativo ao workspace)
_BACKUP_DIR = ".pydeepseek_backups"

# Tamanho máximo de arquivo para escrita (10MB)
_MAX_WRITE_SIZE_BYTES = 10 * 1024 * 1024


class WriteMode(str, Enum):
    """Modos de escrita disponíveis."""
    OVERWRITE = "overwrite"   # Substitui o conteúdo inteiro
    APPEND = "append"         # Adiciona ao final
    INSERT = "insert"         # Insere em linha específica
    PATCH = "patch"           # Substitui intervalo de linhas


class WriteFileTool(BaseTool):
    """
    Escreve ou modifica o conteúdo de um arquivo.

    Modos disponíveis:
      - overwrite : substitui o arquivo inteiro (padrão)
      - append    : adiciona conteúdo ao final do arquivo
      - insert    : insere conteúdo a partir de uma linha específica
      - patch     : substitui um intervalo de linhas (start_line..end_line)

    Cria automaticamente os diretórios intermediários necessários.
    Faz backup automático antes de modificar arquivos existentes.
    """

    name = "write_file"
    description = (
        "Escreve ou modifica o conteúdo de um arquivo. "
        "Modos: 'overwrite' (substitui tudo), 'append' (adiciona ao final), "
        "'insert' (insere em linha específica), 'patch' (substitui intervalo de linhas). "
        "Cria diretórios intermediários automaticamente. "
        "Faz backup automático antes de modificar arquivos existentes."
    )
    category = ToolCategory.FILESYSTEM
    is_destructive = True
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Caminho do arquivo a criar ou modificar.",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Conteúdo a escrever no arquivo.",
            required=True,
        ),
        ToolParameter(
            name="mode",
            type="string",
            description=(
                "Modo de escrita: 'overwrite' (padrão), 'append', 'insert', 'patch'."
            ),
            required=False,
            default="overwrite",
            enum=["overwrite", "append", "insert", "patch"],
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description=(
                "Linha inicial para modos 'insert' e 'patch' (1-based). "
                "Para 'insert': insere ANTES desta linha. "
                "Para 'patch': início do intervalo a substituir."
            ),
            required=False,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description=(
                "Linha final para o modo 'patch' (1-based, inclusive). "
                "O intervalo [start_line, end_line] será substituído pelo conteúdo."
            ),
            required=False,
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="Encoding do arquivo. Default: 'utf-8'.",
            required=False,
            default="utf-8",
        ),
        ToolParameter(
            name="backup",
            type="boolean",
            description=(
                "Se True (padrão), cria backup antes de modificar arquivos existentes. "
                "Backups ficam em .pydeepseek_backups/"
            ),
            required=False,
            default=True,
        ),
    ]

    async def execute(
        self,
        path: str,
        content: str,
        mode: str = "overwrite",
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        encoding: str = "utf-8",
        backup: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Executa a operação de escrita conforme o modo especificado."""
        file_path = Path(path).expanduser().resolve()

        # Valida tamanho do conteúdo
        content_size = len(content.encode(encoding, errors="replace"))
        if content_size > _MAX_WRITE_SIZE_BYTES:
            size_mb = content_size / (1024 * 1024)
            return ToolResult.error(
                error=f"Conteúdo muito grande: {size_mb:.1f}MB (limite: 10MB)",
                output="Divida o conteúdo em partes menores.",
            )

        # Normaliza modo
        try:
            write_mode = WriteMode(mode)
        except ValueError:
            return ToolResult.error(
                error=f"Modo inválido: '{mode}'",
                output=f"Modos válidos: {', '.join(m.value for m in WriteMode)}",
            )

        # Para modos que modificam arquivo existente, ele deve existir
        if write_mode in (WriteMode.APPEND, WriteMode.INSERT, WriteMode.PATCH):
            if not file_path.exists():
                return ToolResult.error(
                    error=f"Arquivo não encontrado para modo '{mode}': {path}",
                    output="Use mode='overwrite' para criar um novo arquivo.",
                )

        # Backup automático
        backup_path: Optional[Path] = None
        if backup and file_path.exists():
            backup_path = _create_backup(file_path)

        # Cria diretórios intermediários
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Executa conforme o modo
        try:
            lines_written, action = _dispatch_write(
                file_path=file_path,
                content=content,
                mode=write_mode,
                start_line=start_line,
                end_line=end_line,
                encoding=encoding,
            )
        except (ValueError, IndexError) as exc:
            return ToolResult.error(
                error=str(exc),
                output=f"Falha na operação de escrita no modo '{mode}'.",
            )
        except OSError as exc:
            return ToolResult.error(
                error=f"Erro de sistema ao escrever '{path}': {exc}",
                output="Verifique permissões de escrita no diretório.",
            )

        # Monta output de confirmação
        file_size = file_path.stat().st_size
        output_lines = [
            f"✅ {action}: {file_path}",
            f"   Linhas escritas : {lines_written}",
            f"   Tamanho final   : {_format_size(file_size)}",
            f"   Encoding        : {encoding}",
        ]
        if backup_path:
            output_lines.append(f"   Backup criado   : {backup_path}")

        return ToolResult.success(
            "\n".join(output_lines),
            file_path=str(file_path),
            lines_written=lines_written,
            file_size=file_size,
            backup_path=str(backup_path) if backup_path else None,
            mode=mode,
        )


# ---------------------------------------------------------------------------
# Dispatcher de modos de escrita
# ---------------------------------------------------------------------------


def _dispatch_write(
    file_path: Path,
    content: str,
    mode: WriteMode,
    start_line: Optional[int],
    end_line: Optional[int],
    encoding: str,
) -> tuple[int, str]:
    """
    Executa a escrita conforme o modo.

    Returns:
        Tupla (linhas_escritas, descrição_da_ação)

    Raises:
        ValueError: Parâmetros inválidos.
        IndexError: Linhas fora do intervalo do arquivo.
        OSError: Erro de sistema.
    """
    new_lines = content.splitlines(keepends=True)
    # Garante newline final
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    if mode == WriteMode.OVERWRITE:
        file_path.write_text(content, encoding=encoding)
        return len(new_lines), "Arquivo criado/sobrescrito"

    if mode == WriteMode.APPEND:
        existing = file_path.read_text(encoding=encoding)
        # Garante separação por newline
        separator = "" if existing.endswith("\n") or not existing else "\n"
        file_path.write_text(existing + separator + content, encoding=encoding)
        return len(new_lines), "Conteúdo adicionado ao final"

    if mode == WriteMode.INSERT:
        if start_line is None:
            raise ValueError("'start_line' é obrigatório para mode='insert'.")
        existing_lines = file_path.read_text(encoding=encoding).splitlines(keepends=True)
        idx = max(0, start_line - 1)
        if idx > len(existing_lines):
            raise IndexError(
                f"start_line={start_line} excede o total de linhas ({len(existing_lines)})."
            )
        result = existing_lines[:idx] + new_lines + existing_lines[idx:]
        file_path.write_text("".join(result), encoding=encoding)
        return len(new_lines), f"Conteúdo inserido antes da linha {start_line}"

    if mode == WriteMode.PATCH:
        if start_line is None or end_line is None:
            raise ValueError("'start_line' e 'end_line' são obrigatórios para mode='patch'.")
        if start_line > end_line:
            raise ValueError(
                f"start_line ({start_line}) deve ser <= end_line ({end_line})."
            )
        existing_lines = file_path.read_text(encoding=encoding).splitlines(keepends=True)
        total = len(existing_lines)
        s = max(0, start_line - 1)
        e = min(total, end_line)
        if s >= total:
            raise IndexError(
                f"start_line={start_line} excede o total de linhas ({total})."
            )
        replaced = e - s
        result = existing_lines[:s] + new_lines + existing_lines[e:]
        file_path.write_text("".join(result), encoding=encoding)
        return len(new_lines), (
            f"Linhas {start_line}–{end_line} substituídas "
            f"({replaced} → {len(new_lines)} linhas)"
        )

    raise ValueError(f"Modo desconhecido: {mode}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_backup(file_path: Path) -> Path:
    """
    Cria uma cópia de backup do arquivo antes de modificá-lo.

    O backup é salvo em .pydeepseek_backups/<timestamp>_<nome>

    Returns:
        Caminho do arquivo de backup criado.
    """
    backup_dir = file_path.parent / _BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"{timestamp}_{file_path.name}"
    backup_path = backup_dir / backup_name

    shutil.copy2(file_path, backup_path)
    return backup_path


def _format_size(size_bytes: int) -> str:
    """Formata tamanho em bytes para string legível."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"
