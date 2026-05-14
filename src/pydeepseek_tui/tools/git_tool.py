"""tools/git_tool.py -- Operacoes Git via subprocess."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any, Optional
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult, ToolStatus

_OPS = ["status", "diff", "log", "add", "commit", "checkout", "branch", "stash", "show"]

class GitTool(BaseTool):
    name = "git"
    description = (
        "Executa operacoes Git no repositorio do projeto. "
        "Leitura (status, diff, log, show) disponivel em todos os modos. "
        "Escrita (add, commit, checkout, branch, stash) requer confirmacao em modo agent."
    )
    category = ToolCategory.GIT
    is_destructive = True
    parameters = [
        ToolParameter("operation", "string", "Operacao Git.", required=True, enum=_OPS),
        ToolParameter("args", "string", "Argumentos extras. Ex: -m mensagem, --all.", required=False, default=""),
        ToolParameter("cwd", "string", "Diretorio do repositorio. Default: cwd.", required=False),
    ]

    async def execute(self, operation: str, args: str = "",
                      cwd: Optional[str] = None, **kw: Any) -> ToolResult:
        if operation not in _OPS:
            return ToolResult.error(error=f"Operacao nao suportada: {operation!r}",
                                    output=f"Disponiveis: {', '.join(_OPS)}")
        work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
        if not work_dir.exists():
            return ToolResult.error(error=f"Diretorio nao encontrado: {cwd}")
        cmd = f"git {operation}" + (f" {args.strip()}" if args and args.strip() else "")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=str(work_dir))
            ob, eb = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            return ToolResult.timeout(60)
        except OSError as exc:
            return ToolResult.error(error=str(exc), output="Verifique se git esta instalado.")
        out = ob.decode("utf-8", errors="replace").strip()
        err = eb.decode("utf-8", errors="replace").strip()
        rc  = proc.returncode or 0
        parts = [f"$ {cmd}"]
        if out: parts.append(out[:10_000])
        if err: parts.append("[stderr]\n" + err[:2000])
        o = "\n".join(parts)
        if rc != 0:
            return ToolResult(status=ToolStatus.ERROR, output=o,
                              error=f"git {operation} exit {rc}",
                              metadata={"rc": rc, "op": operation})
        return ToolResult.success(o, operation=operation)
