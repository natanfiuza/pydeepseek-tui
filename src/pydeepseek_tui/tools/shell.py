"""tools/shell.py -- Execucao de comandos shell com timeout e seguranca."""
from __future__ import annotations
import asyncio, os, shlex
from pathlib import Path
from typing import Any, Optional
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult, ToolStatus

_DEFAULT_TIMEOUT = 30
_MAX_OUT = 20_000
_BLOCKED = {"mkfs", "shutdown", "reboot", "halt"}

class ShellTool(BaseTool):
    name = "shell"
    description = (
        "Executa um comando shell no diretorio de trabalho do projeto. "
        "Use para rodar testes, instalar dependencias, compilar codigo e scripts. "
        "Saida limitada a 20.000 caracteres. Timeout padrao: 30 segundos."
    )
    category = ToolCategory.SHELL
    is_destructive = True
    parameters = [
        ToolParameter("command", "string", "Comando shell a executar.", required=True),
        ToolParameter("cwd", "string", "Diretorio de trabalho. Default: cwd do processo.", required=False),
        ToolParameter("timeout", "integer", "Timeout em segundos (1-300). Default: 30.", required=False, default=30),
        ToolParameter("env", "object", "Variaveis de ambiente extras (dict).", required=False),
    ]

    async def execute(self, command: str, cwd: Optional[str] = None,
                      timeout: int = 30, env: Optional[dict] = None, **kw: Any) -> ToolResult:
        for b in _BLOCKED:
            if command.strip().lower().startswith(b):
                return ToolResult.blocked(f"Comando bloqueado: {b!r}")
        work_dir = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
        if not work_dir.exists():
            return ToolResult.error(error=f"Diretorio nao encontrado: {cwd}")
        t = max(1, min(int(timeout or 30), 300))
        e = os.environ.copy()
        if env and isinstance(env, dict):
            e.update({str(k): str(v) for k, v in env.items()})
        try:
            proc = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=str(work_dir), env=e)
            try:
                ob, eb = await asyncio.wait_for(proc.communicate(), timeout=float(t))
            except asyncio.TimeoutError:
                proc.kill(); await proc.communicate()
                return ToolResult.timeout(t)
        except FileNotFoundError:
            n = shlex.split(command)[0] if command.strip() else command
            return ToolResult.error(error=f"Nao encontrado: {n!r}")
        except OSError as exc:
            return ToolResult.error(error=str(exc))
        out = ob.decode("utf-8", errors="replace")
        err = eb.decode("utf-8", errors="replace")
        rc  = proc.returncode or 0
        parts = [f"$ {command}", f"[exit {rc}]"]
        if out.strip(): parts.append(out[:_MAX_OUT] + ("..." if len(out) > _MAX_OUT else ""))
        if err.strip(): parts.append("[stderr]\n" + err[:_MAX_OUT])
        o = "\n".join(parts)
        if rc != 0:
            return ToolResult(status=ToolStatus.ERROR, output=o,
                              error=f"exit code {rc}", metadata={"rc": rc})
        return ToolResult.success(o, returncode=rc, cwd=str(work_dir))
