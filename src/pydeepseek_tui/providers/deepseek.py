"""
providers/deepseek.py
=====================

Provider DeepSeek — implementação padrão do pydeepseek-tui.

Utiliza o SDK oficial da OpenAI (compatível com a API DeepSeek),
com suporte a:
  - Streaming de respostas
  - Function calling (tool use)
  - Thinking mode (chain-of-thought via reasoning_content)
  - Modelos: deepseek-v4-pro, deepseek-chat, deepseek-reasoner

Documentação da API DeepSeek:
  https://api-docs.deepseek.com
"""

from __future__ import annotations

import json
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

# Modelos DeepSeek conhecidos (Mai/2026)
_DEEPSEEK_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        context_window=1_000_000,
        supports_tools=True,
        supports_thinking=True,
        description="Modelo principal — máxima capacidade de raciocínio e coding",
    ),
    ModelInfo(
        id="deepseek-chat",
        name="DeepSeek Chat",
        context_window=65_536,
        supports_tools=True,
        supports_thinking=False,
        description="Modelo de chat geral, rápido e econômico",
    ),
    ModelInfo(
        id="deepseek-reasoner",
        name="DeepSeek Reasoner (R1)",
        context_window=65_536,
        supports_tools=False,
        supports_thinking=True,
        description="Especializado em raciocínio matemático e lógico",
    ),
    ModelInfo(
        id="deepseek-coder-v2",
        name="DeepSeek Coder V2",
        context_window=128_000,
        supports_tools=True,
        supports_thinking=False,
        description="Especializado em geração e revisão de código",
    ),
]

# Preços DeepSeek V4 Pro (USD por 1M tokens — referência Mai/2026)
_PRICE_INPUT_PER_M = 0.27
_PRICE_OUTPUT_PER_M = 1.10


class DeepSeekProvider(BaseProvider):
    """
    Provider para a API DeepSeek.

    Usa o AsyncOpenAI SDK apontando para o endpoint DeepSeek,
    que é totalmente compatível com o formato OpenAI Chat Completions.

    Exemplo:
        provider = DeepSeekProvider(
            api_key="sk-...",
            model="deepseek-v4-pro",
        )
        async for chunk in provider.stream(messages, tools=tool_schemas):
            print(chunk.content, end="")
    """

    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-pro",
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
        return "DeepSeek"

    # ------------------------------------------------------------------
    # chat() — resposta completa
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> ChatResponse:
        """Envia mensagens e aguarda a resposta completa (não-streaming)."""
        api_messages = self._build_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except APIConnectionError as exc:
            raise ConnectionError(
                f"Não foi possível conectar à API DeepSeek: {exc}"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout ao conectar à API DeepSeek (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Erro da API DeepSeek [{exc.status_code}]: {exc.message}"
            ) from exc

        choice = response.choices[0]
        msg = choice.message

        # Thinking mode — DeepSeek retorna em reasoning_content
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
            # Reasoning tokens (thinking mode)
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
    # stream() — streaming de resposta
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Gera chunks de resposta em streaming.

        Emite:
          - StreamChunk(thinking=...) durante o chain-of-thought
          - StreamChunk(content=...) durante a resposta
          - StreamChunk(tool_call_delta=...) durante tool calls
          - StreamChunk(is_final=True, usage=...) ao finalizar
        """
        api_messages = self._build_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Acumuladores para tool calls parciais
        tool_calls_buffer: dict[int, dict[str, Any]] = {}
        finish_reason: str = "stop"
        usage: Optional[UsageStats] = None
        model_name: str = self.model

        try:
            async with await self._client.chat.completions.create(**kwargs) as stream:
                async for raw_chunk in stream:
                    raw_chunk: ChatCompletionChunk

                    if not raw_chunk.choices and raw_chunk.usage:
                        # Chunk final com usage (stream_options)
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

                    # ── Thinking mode (reasoning_content) ──────────────
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        yield StreamChunk(thinking=delta.reasoning_content)
                        continue

                    # ── Conteúdo de texto ───────────────────────────────
                    if delta.content:
                        yield StreamChunk(content=delta.content)
                        continue

                    # ── Tool calls parciais ─────────────────────────────
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
                f"Conexão perdida durante streaming: {exc}"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout durante streaming (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Erro da API DeepSeek durante streaming [{exc.status_code}]: {exc.message}"
            ) from exc

        # Emite tool calls completos acumulados
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

        # Chunk final com metadados
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
        """
        Retorna os modelos DeepSeek disponíveis.

        Tenta buscar da API; usa lista local como fallback.
        """
        try:
            response = await self._client.models.list()
            api_models = [m.id for m in response.data]

            # Filtra os modelos conhecidos que estão disponíveis na API
            available = [m for m in _DEEPSEEK_MODELS if m.id in api_models]

            # Adiciona modelos da API não mapeados localmente
            known_ids = {m.id for m in _DEEPSEEK_MODELS}
            for model_id in api_models:
                if model_id not in known_ids:
                    available.append(
                        ModelInfo(
                            id=model_id,
                            name=model_id,
                            description="Modelo disponível na API",
                        )
                    )

            return available if available else _DEEPSEEK_MODELS

        except Exception:
            logger.warning("Não foi possível listar modelos da API DeepSeek. Usando lista local.")
            return _DEEPSEEK_MODELS

    # ------------------------------------------------------------------
    # health_check()
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Verifica conectividade com a API DeepSeek.
        Envia uma requisição mínima para validar a API key.
        """
        try:
            await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                stream=False,
            )
            return True
        except APIStatusError as exc:
            if exc.status_code == 401:
                logger.error("API key DeepSeek inválida ou expirada.")
            else:
                logger.error("Erro de status DeepSeek: %s", exc.status_code)
            return False
        except Exception as exc:
            logger.error("Health check DeepSeek falhou: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Estimativa de custo
    # ------------------------------------------------------------------

    def estimate_cost(self, usage: UsageStats) -> float:
        """Calcula o custo estimado em USD para o uso informado."""
        input_cost = (usage.prompt_tokens / 1_000_000) * _PRICE_INPUT_PER_M
        output_cost = (usage.completion_tokens / 1_000_000) * _PRICE_OUTPUT_PER_M
        return round(input_cost + output_cost, 6)
