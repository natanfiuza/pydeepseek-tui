"""
providers/base.py
=================

Interface abstrata para todos os providers de IA.

Todo provider deve herdar de BaseProvider e implementar:
  - chat()    : resposta completa (não-streaming)
  - stream()  : resposta em streaming (gerador assíncrono)
  - list_models(): lista de modelos disponíveis

Tipos compartilhados:
  - Message      : mensagem no formato {role, content}
  - ToolCall     : chamada de tool pelo modelo
  - ChatResponse : resposta completa do modelo
  - StreamChunk  : fragmento de resposta em streaming
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MessageRole(str, Enum):
    """Papéis possíveis em uma mensagem de chat."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ---------------------------------------------------------------------------
# Tipos de dados
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """
    Representa uma mensagem no histórico de conversa.

    Compatível com o formato OpenAI Chat Completions API.
    """

    role: MessageRole
    content: str
    tool_call_id: Optional[str] = None   # Usado em respostas de tools
    name: Optional[str] = None           # Nome da tool (quando role=tool)

    def to_dict(self) -> dict[str, Any]:
        """Serializa para o formato esperado pela API OpenAI-compatible."""
        data: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.name:
            data["name"] = self.name
        return data

    @classmethod
    def system(cls, content: str) -> "Message":
        """Atalho para criar mensagem de sistema."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        """Atalho para criar mensagem do usuário."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        """Atalho para criar mensagem do assistente."""
        return cls(role=MessageRole.ASSISTANT, content=content)

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str) -> "Message":
        """Atalho para criar mensagem de resultado de tool."""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )


@dataclass
class ToolCallFunction:
    """Função chamada dentro de um ToolCall."""

    name: str
    arguments: str  # JSON string com os argumentos


@dataclass
class ToolCall:
    """
    Representa uma chamada de tool solicitada pelo modelo.

    Formato compatível com OpenAI function calling.
    """

    id: str
    function: ToolCallFunction
    type: str = "function"

    @property
    def tool_name(self) -> str:
        return self.function.name

    @property
    def arguments_raw(self) -> str:
        return self.function.arguments


@dataclass
class UsageStats:
    """Estatísticas de uso de tokens de uma requisição."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0   # Tokens de thinking mode (DeepSeek/o1)

    @property
    def estimated_cost_usd(self) -> float:
        """
        Estimativa de custo em USD.
        Valores baseados no DeepSeek V3/V4 (referência Mai/2026).
        Sobrescreva em cada provider com os preços corretos.
        """
        input_cost = (self.prompt_tokens / 1_000_000) * 0.27
        output_cost = (self.completion_tokens / 1_000_000) * 1.10
        return round(input_cost + output_cost, 6)


@dataclass
class ChatResponse:
    """Resposta completa de uma requisição de chat (não-streaming)."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: Optional[str] = None        # Chain-of-thought (thinking mode)
    usage: UsageStats = field(default_factory=UsageStats)
    model: str = ""
    finish_reason: str = "stop"

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def has_thinking(self) -> bool:
        return bool(self.thinking)


@dataclass
class StreamChunk:
    """
    Fragmento de resposta em streaming.

    O gerador assíncrono stream() emite uma sequência de StreamChunks.
    O consumidor (AgentLoop / widget de chat) acumula os chunks.
    """

    # Tipos de chunk
    content: str = ""             # Fragmento de texto da resposta
    thinking: str = ""            # Fragmento de chain-of-thought
    tool_call_delta: Optional[ToolCall] = None  # Fragmento de tool call

    # Metadados (presentes apenas no chunk final: is_final=True)
    is_final: bool = False
    usage: Optional[UsageStats] = None
    finish_reason: str = ""
    model: str = ""

    @property
    def is_thinking_chunk(self) -> bool:
        return bool(self.thinking) and not self.content

    @property
    def is_content_chunk(self) -> bool:
        return bool(self.content)

    @property
    def is_tool_call_chunk(self) -> bool:
        return self.tool_call_delta is not None


@dataclass
class ModelInfo:
    """Informações sobre um modelo disponível no provider."""

    id: str
    name: str
    context_window: int = 0
    supports_tools: bool = True
    supports_thinking: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Interface abstrata
# ---------------------------------------------------------------------------


class BaseProvider(ABC):
    """
    Contrato que todo provider de IA deve implementar.

    Uso:
        provider = DeepSeekProvider(api_key="sk-...", model="deepseek-v4-pro")
        response = await provider.chat(messages, tools=tools)

        async for chunk in provider.stream(messages, tools=tools):
            print(chunk.content, end="", flush=True)
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        timeout: int = 120,
        max_tokens: int = 8192,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nome legível do provider (ex: 'DeepSeek', 'OpenAI')."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> ChatResponse:
        """
        Envia mensagens e aguarda a resposta completa.

        Args:
            messages: Histórico de mensagens da conversa.
            tools: Lista de schemas JSON das tools disponíveis.
            system_prompt: Prompt de sistema (sobrescreve mensagem system no histórico).
            temperature: Criatividade do modelo (0.0 a 1.0).

        Returns:
            ChatResponse com o conteúdo completo e metadados.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Envia mensagens e retorna um gerador assíncrono de StreamChunks.

        O último chunk terá is_final=True e conterá usage e finish_reason.

        Args:
            messages: Histórico de mensagens da conversa.
            tools: Lista de schemas JSON das tools disponíveis.
            system_prompt: Prompt de sistema.
            temperature: Criatividade do modelo.

        Yields:
            StreamChunk com fragmentos de conteúdo, thinking ou tool_calls.
        """
        ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """
        Lista os modelos disponíveis neste provider.

        Returns:
            Lista de ModelInfo ordenada por relevância.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifica se o provider está acessível e a API key é válida.

        Returns:
            True se o provider estiver operacional.
        """
        ...

    def _build_messages(
        self,
        messages: list[Message],
        system_prompt: Optional[str],
    ) -> list[dict[str, Any]]:
        """
        Constrói a lista de dicts de mensagens para a API,
        injetando o system_prompt se fornecido.
        """
        result: list[dict[str, Any]] = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            # Evita duplicar system prompt se já existe no histórico
            if msg.role == MessageRole.SYSTEM and system_prompt:
                continue
            result.append(msg.to_dict())

        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"
