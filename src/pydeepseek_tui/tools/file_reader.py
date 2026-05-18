import os
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.sandbox import is_path_allowed


class FileReaderTool(BaseTool):

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Le e devolve o conteudo de um ficheiro de texto local. "
            "Usa esta ferramenta quando precisares de analisar ou extrair "
            "informacoes de um ficheiro. Apenas ficheiros dentro do diretorio "
            "de trabalho atual podem ser lidos."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "O caminho absoluto ou relativo para o ficheiro que deve ser lido.",
                }
            },
            "required": ["file_path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path")

        if not file_path:
            return "Erro: O caminho do ficheiro (file_path) nao foi fornecido."

        if not is_path_allowed(str(file_path)):
            return (
                f"Erro de seguranca: O ficheiro '{file_path}' esta fora "
                "do diretorio de trabalho. Apenas ficheiros dentro do "
                "projeto atual podem ser lidos."
            )

        try:
            if not os.path.exists(file_path):
                return f"Erro: O ficheiro '{file_path}' nao foi encontrado."

            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            return f"Erro ao tentar ler o ficheiro: {str(e)}"
