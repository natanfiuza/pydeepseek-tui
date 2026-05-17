from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    """
    Interface base para todas as ferramentas (tools) do agente.
    Define o contrato necessario para integracao com chamadas de funcao (Function Calling).
    """

    is_destructive: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador da ferramenta (ex: 'read_file')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Descrição detalhada do que a ferramenta faz. É essencial para a IA entender quando usá-la."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Schema JSON (OpenAI Format) dos parâmetros exigidos pela ferramenta."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Executa a ação da ferramenta com os argumentos fornecidos pela IA.
        
        Args:
            **kwargs: Parâmetros dinâmicos definidos no schema.
            
        Returns:
            str: O resultado da execução no formato de texto para retornar ao modelo.
        """
        pass