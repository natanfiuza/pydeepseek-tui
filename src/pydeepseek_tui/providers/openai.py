"""
providers/openai.py
===================

Provider OpenAI — suporte a GPT-4o, GPT-4-turbo e demais modelos OpenAI.

Estruturalmente idêntico ao DeepSeekProvider, pois ambos usam o mesmo
SDK (openai) e o mesmo formato de API (Chat Completions).

A principal diferença está nos endpoints, preços e nos campos
específicos de cada API (ex: reasoning_content no DeepSeek vs
usage.completion_tokens_details.reasoning_tokens no o1/o3).

Modelos suportados (Mai/2026):
  - gpt-4o, gpt-4o-mini
  - gpt-4-turbo
  - o3, o3-mini (thinking nativo)
  - o4-mini
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError
from openai.types.chat import ChatCompletionChunk

from pydeepseek_tui.providers.base import (
    BaseProvider,
    ChatResponse,
    Message,
    MessageRole,
    ModelInfo,
    StreamChunk,
    ToolCall,
    ToolCallFunction,
    UsageStats,
)

logger = logging.getLogger(__name__)

# Modelos OpenAI conhecidos (Mai/2026)
_OPENAI_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        context_window=128_000,
        supports_tools=True,
        supports_thinking=False,
        description="Modelo principal da OpenAI — multimodal e rápido",
    ),
    ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        context_window=128_000,
        supports_tools=True,
        supports_thinking=False,
        description="Versão econômica do GPT-4o",
    ),
    ModelInfo(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        context_window=128_000,
        supports_tools=True,
        supports_thinking=False,
        description="GPT-4 com janela de contexto ampliada",
    ),
    ModelInfo(
        id="o3",
        name="o3",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=True,
        description="Modelo de raciocínio avançado da OpenAI",
    ),
    ModelInfo(
        id="o3-mini",
        name="o3 Mini",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=True,
        description="Versão compacta do o3 — rápido e econômico",
    ),
    ModelInfo(
        id="o4-mini",
        name="o4 Mini",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=True,
        description="Modelo de raciocínio de próxima geração",
    ),
]

# Preços OpenAI GPT-4o (USD por 1M tokens — referência Mai/2026)
_PRICE_INPUT_PER_M = 2.50
_PRICE_OUTPUT_PER_M = 10.00


class OpenAIProvider(BaseProvider):
    """
    Provider para a API OpenAI.

    Suporta todos os modelos GPT-4o e da série o1/o3/o4,
    incluindo thinking mode (chain-of-thought) nos modelos de raciocínio.

    Exemplo:
        provider = OpenAIProvider(
            api_key="sk-...",
            model="gpt-4o",
        )
        response = await provider.chat(messages, tools=tool_schemas)
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    # Modelos que suportam thinking nativo (reasoning_effort)
    _THINKING_MODELS = {"o1", "o1-mini", "o3", "o3-mini", "o4-mini"}

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 120,
        max_tokens: int = 8192,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or self.DEFAULT_BASE_URL,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=float(self.timeout),
        )

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def _is_thinking_model(self) -> bool:
        """Verifica se o modelo atual suporta thinking mode."""
        return self.model in self._THINKING_MODELS

    def _build_kwargs(
        self,
        api_messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        temperature: float,
        stream: bool,
    ) -> dict[str, Any]:
        """
        Constrói os kwargs para a chamada da API.

        Modelos de raciocínio (o1/o3/o4) não aceitam 'temperature'
        e usam 'max_completion_tokens' em vez de 'max_tokens'.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "stream": stream,
        }

        if self._is_thinking_model:
            # Modelos de raciocínio usam max_completion_tokens
            kwargs["max_completion_tokens"] = self.max_tokens
        else:
            kwargs["max_tokens"] = self.max_tokens
            kwargs["temperature"] = temperature

        if tools and not self._is_thinking_model:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        elif tools and self._is_thinking_model:
            # o3/o4 suportam tools com restrições
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream:
            kwargs["stream_options"] = {"include_usage": True}

        return kwargs

    # ------------------------------------------------------------------
    # chat()
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> ChatResponse:
        """Envia mensagens e aguarda a resposta completa."""
        api_messages = self._build_messages(messages, system_prompt)
        kwargs = self._build_kwargs(api_messages, tools, temperature, stream=False)

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except APIConnectionError as exc:
            raise ConnectionError(
                f"Não foi possível conectar à API OpenAI: {exc}"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout ao conectar à API OpenAI (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Erro da API OpenAI [{exc.status_code}]: {exc.message}"
            ) from exc

        choice = response.choices[0]
        msg = choice.message

        # Thinking mode — modelos o1/o3 retornam em reasoning_content (beta)
        thinking: Optional[str] = None
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            thinking = msg.reasoning_content

        # Tool calls
        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        function=ToolCallFunction(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                )

        # Usage
        usage = UsageStats()
        if response.usage:
            usage.prompt_tokens = response.usage.prompt_tokens
            usage.completion_tokens = response.usage.completion_tokens
            usage.total_tokens = response.usage.total_tokens
            if hasattr(response.usage, "completion_tokens_details"):
                details = response.usage.completion_tokens_details
                if details and hasattr(details, "reasoning_tokens"):
                    usage.reasoning_tokens = details.reasoning_tokens or 0

        return ChatResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            thinking=thinking,
            usage=usage,
            model=response.model,
            finish_reason=choice.finish_reason or "stop",
        )

    # ------------------------------------------------------------------
    # stream()
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Gera chunks de resposta em streaming."""
        api_messages = self._build_messages(messages, system_prompt)
        kwargs = self._build_kwargs(api_messages, tools, temperature, stream=True)

        tool_calls_buffer: dict[int, dict[str, Any]] = {}
        finish_reason: str = "stop"
        usage: Optional[UsageStats] = None
        model_name: str = self.model

        try:
            async with await self._client.chat.completions.create(**kwargs) as stream:
                async for raw_chunk in stream:
                    raw_chunk: ChatCompletionChunk

                    # Chunk final com usage
                    if not raw_chunk.choices and raw_chunk.usage:
                        u = raw_chunk.usage
                        usage = UsageStats(
                            prompt_tokens=u.prompt_tokens,
                            completion_tokens=u.completion_tokens,
                            total_tokens=u.total_tokens,
                        )
                        if hasattr(u, "completion_tokens_details"):
                            details = u.completion_tokens_details
                            if details and hasattr(details, "reasoning_tokens"):
                                usage.reasoning_tokens = details.reasoning_tokens or 0
                        continue

                    if not raw_chunk.choices:
                        continue

                    choice = raw_chunk.choices[0]
                    delta = choice.delta
                    model_name = raw_chunk.model or self.model

                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

                    # Thinking mode (o1/o3/o4)
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        yield StreamChunk(thinking=delta.reasoning_content)
                        continue

                    # Conteúdo de texto
                    if delta.content:
                        yield StreamChunk(content=delta.content)
                        continue

                    # Tool calls parciais
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }
                            buf = tool_calls_buffer[idx]
                            if tc_delta.id:
                                buf["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    buf["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    buf["arguments"] += tc_delta.function.arguments

        except APIConnectionError as exc:
            raise ConnectionError(
                f"Conexão perdida durante streaming OpenAI: {exc}"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout durante streaming OpenAI (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Erro da API OpenAI durante streaming [{exc.status_code}]: {exc.message}"
            ) from exc

        # Emite tool calls completos
        for buf in tool_calls_buffer.values():
            if buf["name"]:
                yield StreamChunk(
                    tool_call_delta=ToolCall(
                        id=buf["id"],
                        function=ToolCallFunction(
                            name=buf["name"],
                            arguments=buf["arguments"],
                        ),
                    )
                )

        # Chunk final
        yield StreamChunk(
            is_final=True,
            finish_reason=finish_reason,
            usage=usage or UsageStats(),
            model=model_name,
        )

    # ------------------------------------------------------------------
    # list_models()
    # ------------------------------------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        """Lista modelos OpenAI disponíveis na conta."""
        try:
            response = await self._client.models.list()
            api_ids = {m.id for m in response.data}

            available = [m for m in _OPENAI_MODELS if m.id in api_ids]

            # Modelos da API não mapeados localmente
            known_ids = {m.id for m in _OPENAI_MODELS}
            for model_id in sorted(api_ids):
                if model_id not in known_ids and model_id.startswith(("gpt-", "o1", "o3", "o4")):
                    available.append(
                        ModelInfo(
                            id=model_id,
                            name=model_id.upper(),
                            description="Modelo disponível na API OpenAI",
                        )
                    )

            return available if available else _OPENAI_MODELS

        except Exception:
            logger.warning("Não foi possível listar modelos da API OpenAI. Usando lista local.")
            return _OPENAI_MODELS

    # ------------------------------------------------------------------
    # health_check()
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verifica conectividade e validade da API key OpenAI."""
        try:
            await self._client.models.list()
            return True
        except APIStatusError as exc:
            if exc.status_code == 401:
                logger.error("API key OpenAI inválida ou expirada.")
            else:
                logger.error("Erro de status OpenAI: %s", exc.status_code)
            return False
        except Exception as exc:
            logger.error("Health check OpenAI falhou: %s", exc)
            return False

    def estimate_cost(self, usage: UsageStats) -> float:
        """Calcula custo estimado em USD para GPT-4o."""
        input_cost = (usage.prompt_tokens / 1_000_000) * _PRICE_INPUT_PER_M
        output_cost = (usage.completion_tokens / 1_000_000) * _PRICE_OUTPUT_PER_M
        return round(input_cost + output_cost, 6)
