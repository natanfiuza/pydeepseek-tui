import asyncio
import os
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.sandbox import is_path_allowed


class ShellTool(BaseTool):
    """Executa comandos shell com timeout e sandbox."""

    is_destructive = True

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return (
            "Executa um comando shell e devolve stdout, stderr e exit code. "
            "ATENCAO: Comandos destrutivos (rm, format, del /s, etc) serao "
            "executados com confirmacao previa. Usa com cuidado. "
            "O comando corre dentro do diretorio de trabalho do projeto."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "O comando shell a executar.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout em segundos (default 30, max 120).",
                    "default": 30,
                },
                "cwd": {
                    "type": "string",
                    "description": "Diretorio de trabalho. Default: diretorio atual.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> str:
        command = kwargs.get("command")
        timeout = min(kwargs.get("timeout", 30), 120)
        cwd = kwargs.get("cwd") or os.getcwd()

        if not command:
            return "Erro: O comando (command) nao foi fornecido."

        cwd_str = str(cwd)
        if not is_path_allowed(cwd_str):
            return (
                f"Erro de seguranca: O diretorio '{cwd_str}' esta fora "
                "do diretorio de trabalho."
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_str,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return f"Erro: O comando excedeu o timeout de {timeout}s."

            out = stdout.decode("utf-8", errors="replace")[:8000]
            err = stderr.decode("utf-8", errors="replace")[:8000]

            parts = [f"Exit code: {proc.returncode}"]
            if out:
                parts.append(f"stdout:\n{out}")
            if err:
                parts.append(f"stderr:\n{err}")

            return "\n\n".join(parts)

        except Exception as e:
            return f"Erro ao executar o comando: {str(e)}"
