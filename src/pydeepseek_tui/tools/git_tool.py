import asyncio
import os
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.sandbox import is_path_allowed

READ_ONLY_ACTIONS = {"status", "diff", "log", "branch"}
DESTRUCTIVE_ACTIONS = {"add", "commit"}


class GitTool(BaseTool):
    """Ferramenta para operacoes Git."""

    is_destructive = True

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return (
            "Executa operacoes Git num repositorio local. "
            "Acoes disponiveis: status, diff, log, branch, add, commit. "
            "Acoes add e commit requerem confirmacao explicita (overwrite=true)."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "diff", "log", "branch", "add", "commit"],
                    "description": "Acao git a executar.",
                },
                "path": {
                    "type": "string",
                    "description": "Caminho do repositorio. Default: diretorio atual.",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ficheiros para 'add'. Apenas para acao 'add'.",
                },
                "message": {
                    "type": "string",
                    "description": "Mensagem de commit. Apenas para acao 'commit'.",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Confirmacao para acoes destrutivas (add/commit).",
                    "default": False,
                },
            },
            "required": ["action"],
        }

    async def _run_git(self, *args: str, cwd: str) -> tuple[int, str, str]:
        cmd = ["git"] + list(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode("utf-8", errors="replace")[:8000]
        err = stderr.decode("utf-8", errors="replace")[:8000]
        code = proc.returncode if proc.returncode is not None else -1
        return code, out, err

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action")
        path_str = kwargs.get("path") or os.getcwd()
        overwrite = kwargs.get("overwrite", False)

        if not action:
            return "Erro: A acao (action) nao foi fornecida."

        if action not in READ_ONLY_ACTIONS and action not in DESTRUCTIVE_ACTIONS:
            return f"Erro: Acao desconhecida '{action}'. Acoes validas: {', '.join(sorted(READ_ONLY_ACTIONS | DESTRUCTIVE_ACTIONS))}."

        if not is_path_allowed(str(path_str)):
            return (
                f"Erro de seguranca: O caminho '{path_str}' esta fora "
                "do diretorio de trabalho."
            )

        if action in DESTRUCTIVE_ACTIONS and not overwrite:
            return (
                f"A acao '{action}' e destrutiva. Para confirmares, "
                "chama novamente com overwrite=true."
            )

        try:
            if action == "status":
                code, out, err = await self._run_git("status", "--short", cwd=path_str)
                if code == 0:
                    return (
                        f"Git status em '{path_str}':\n{out or '(working tree limpo)'}"
                    )
                return f"Erro git status:\n{err}"

            if action == "diff":
                code, out, err = await self._run_git("diff", cwd=path_str)
                code2, out2, err2 = await self._run_git(
                    "diff", "--staged", cwd=path_str
                )
                parts = []
                if out:
                    parts.append(f"Unstaged diff:\n{out}")
                if out2:
                    parts.append(f"Staged diff:\n{out2}")
                if not parts:
                    parts.append("(sem diferencas)")
                return "\n\n".join(parts)

            if action == "log":
                code, out, err = await self._run_git(
                    "log",
                    "--oneline",
                    "-10",
                    "--decorate",
                    cwd=path_str,
                )
                if code == 0:
                    return f"Ultimos 10 commits:\n{out or '(sem commits)'}"
                return f"Erro git log:\n{err}"

            if action == "branch":
                code, out, err = await self._run_git("branch", "--list", cwd=path_str)
                if code == 0:
                    return f"Branches em '{path_str}':\n{out}"
                return f"Erro git branch:\n{err}"

            if action == "add":
                files = kwargs.get("files", [])
                if not files:
                    return "Erro: Especifica pelo menos um ficheiro para 'add'."
                code, out, err = await self._run_git("add", *files, cwd=path_str)
                if code == 0:
                    return f"Git add: {', '.join(files)} adicionados."
                return f"Erro git add:\n{err}"

            if action == "commit":
                message = kwargs.get("message", "")
                if not message:
                    return "Erro: Uma mensagem (message) e obrigatoria para commit."
                code, out, err = await self._run_git(
                    "commit", "-m", message, cwd=path_str
                )
                if code == 0:
                    return f"Git commit realizado:\n{out}"
                return f"Erro git commit:\n{err}"

            return f"Erro: Acao '{action}' nao implementada."

        except Exception as e:
            return f"Erro ao executar git {action}: {str(e)}"
