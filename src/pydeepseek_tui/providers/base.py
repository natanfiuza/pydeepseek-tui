from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any

class BaseAIProvider(ABC):
    """
    Interface abstrata (contrato) para provedores de IA.
    Qualquer nova integração (DeepSeek, OpenAI, Claude) deve herdar desta classe.
    """

    @abstractmethod
    async def ask(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None) -> Any:
        """
        Processa a requisição com o histórico completo e ferramentas.
        """
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None) -> AsyncGenerator[Any, None]:
        """
        Processa a requisicao em streaming com o historico e ferramentas.
        """
        pass

    async def close(self) -> None:
        """Fecha recursos do provedor. Metodo opcional para limpeza."""
        pass