import os
from typing import Any, Dict
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.sandbox import is_path_allowed


class WriteFileTool(BaseTool):

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Cria ou substitui um ficheiro local com o conteudo fornecido. "
            "Usa esta ferramenta quando precisares de guardar codigo, notas "
            "ou gerar novos ficheiros. Para sobrescrever um ficheiro existente "
            "define overwrite como true."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "O caminho (absoluto ou relativo) onde o ficheiro sera guardado.",
                },
                "content": {
                    "type": "string",
                    "description": "O conteudo de texto a ser escrito no ficheiro.",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Define como true para sobrescrever um ficheiro ja existente. O padrao e false.",
                    "default": False,
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path")
        content = kwargs.get("content")
        overwrite = kwargs.get("overwrite", False)

        if not file_path or content is None:
            return (
                "Erro: O caminho do ficheiro (file_path) ou o conteudo (content) "
                "nao foram fornecidos."
            )

        if not is_path_allowed(str(file_path)):
            return (
                f"Erro de seguranca: O caminho '{file_path}' esta fora "
                "do diretorio de trabalho."
            )

        try:
            if os.path.exists(file_path) and not overwrite:
                return (
                    f"O ficheiro '{file_path}' ja existe. Para sobrescreve-lo, "
                    "chama novamente a ferramenta com overwrite=true."
                )

            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)

            return (
                f"Sucesso: Ficheiro '{file_path}' guardado corretamente "
                f"com {len(content)} caracteres."
            )
        except Exception as e:
            return f"Erro ao tentar guardar o ficheiro: {str(e)}"
