"""
providers/anthropic.py
======================

Provider Anthropic — suporte a Claude 3.5, Claude 3.7 e demais modelos.

Diferente dos outros providers, a Anthropic usa seu próprio SDK
(anthropic) com um formato de API distinto do OpenAI:
  - Mensagens system são passadas como parâmetro separado
  - Tool use tem formato próprio (input_schema em vez de parameters)
  - Thinking mode é ativado via parâmetro "thinking" dedicado
  - Streaming usa eventos tipados (content_block_delta, etc.)

Documentação: https://docs.anthropic.com/en/api
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

import anthropic
from anthropic import AsyncAnthropic, APIConnectionError, APIStatusError, APITimeoutError
from anthropic.types import (
    ContentBlockDeltaEvent,
    MessageDeltaEvent,
    MessageStartEvent,
    MessageStreamEvent,
)

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

# Modelos Anthropic conhecidos (Mai/2026)
_ANTHROPIC_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="claude-3-7-sonnet-20250219",
        name="Claude 3.7 Sonnet",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=True,
        description="Modelo mais inteligente da Anthropic com thinking híbrido",
    ),
    ModelInfo(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=False,
        description="Melhor equilíbrio entre inteligência e velocidade",
    ),
    ModelInfo(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=False,
        description="Modelo mais rápido e econômico da Anthropic",
    ),
    ModelInfo(
        id="claude-3-opus-20240229",
        name="Claude 3 Opus",
        context_window=200_000,
        supports_tools=True,
        supports_thinking=False,
        description="Modelo Claude 3 de maior capacidade",
    ),
]

# Preços Claude 3.5 Sonnet (USD por 1M tokens — referência Mai/2026)
_PRICE_INPUT_PER_M = 3.00
_PRICE_OUTPUT_PER_M = 15.00

# Modelos que suportam thinking mode estendido
_THINKING_MODELS = {"claude-3-7-sonnet-20250219"}


class AnthropicProvider(BaseProvider):
    """
    Provider para a API Anthropic (Claude).

    Usa o SDK nativo da Anthropic, que difere do formato OpenAI
    em vários aspectos — principalmente no formato de tools,
    mensagens system e thinking mode.

    Exemplo:
        provider = AnthropicProvider(
            api_key="sk-ant-...",
            model="claude-3-5-sonnet-20241022",
        )
        async for chunk in provider.stream(messages, tools=tool_schemas):
            print(chunk.content, end="")
    """

    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 120,
        max_tokens: int = 8192,
        enable_thinking: bool = False,
        thinking_budget_tokens: int = 5000,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or self.DEFAULT_BASE_URL,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        self.enable_thinking = enable_thinking and model in _THINKING_MODELS
        self.thinking_budget_tokens = thinking_budget_tokens

        self._client = AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=float(self.timeout),
        )

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    # ------------------------------------------------------------------
    # Conversão de formatos
    # ------------------------------------------------------------------

    def _convert_messages(
        self,
        messages: list[Message],
        system_prompt: Optional[str],
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Converte mensagens do formato interno para o formato Anthropic.

        A Anthropic:
          - Recebe 'system' como parâmetro separado (não na lista de mensagens)
          - Exige que mensagens alternem entre 'user' e 'assistant'
          - Não aceita mensagens 'system' na lista

        Returns:
            Tupla (system_text, messages_list)
        """
        system_text = system_prompt or ""
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Acumula system messages no system_text
                if system_text:
                    system_text += f"\n\n{msg.content}"
                else:
                    system_text = msg.content
                continue

            if msg.role == MessageRole.TOOL:
                # Resultado de tool — formato Anthropic
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id or "",
                            "content": msg.content,
                        }
                    ],
                })
                continue

            anthropic_messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        return system_text, anthropic_messages

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Converte schemas de tools do formato OpenAI para o formato Anthropic.

        OpenAI:
            {"type": "function", "function": {"name": ..., "parameters": {...}}}

        Anthropic:
            {"name": ..., "description": ..., "input_schema": {...}}
        """
        anthropic_tools: list[dict[str, Any]] = []

        for tool in tools:
            if tool.get("type") == "function":
                fn = tool.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                })
            else:
                # Já no formato Anthropic
                anthropic_tools.append(tool)

        return anthropic_tools

    def _build_request_kwargs(
        self,
        system_text: str,
        anthropic_messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        temperature: float,
    ) -> dict[str, Any]:
        """Constrói os kwargs comuns para chat() e stream()."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": self.max_tokens,
        }

        if system_text:
            kwargs["system"] = system_text

        # Thinking mode (Claude 3.7+)
        if self.enable_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens,
            }
            # Thinking mode requer temperature=1
            kwargs["temperature"] = 1.0
        else:
            kwargs["temperature"] = temperature

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

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
        """Envia mensagens e aguarda resposta completa da API Anthropic."""
        system_text, anthropic_messages = self._convert_messages(messages, system_prompt)
        kwargs = self._build_request_kwargs(
            system_text, anthropic_messages, tools, temperature
        )

        try:
            response = await self._client.messages.create(**kwargs)
        except APIConnectionError as exc:
            raise ConnectionError(
                f"Não foi possível conectar à API Anthropic: {exc}"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout ao conectar à API Anthropic (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Erro da API Anthropic [{exc.status_code}]: {exc.message}"
            ) from exc

        # Extrai conteúdo, thinking e tool calls dos blocos de conteúdo
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "thinking":
                thinking_parts.append(block.thinking)
            elif block.type == "tool_use":
                import json
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        function=ToolCallFunction(
                            name=block.name,
                            arguments=json.dumps(block.input),
                        ),
                    )
                )

        # Usage
        usage = UsageStats(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

        return ChatResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            thinking="\n\n".join(thinking_parts) or None,
            usage=usage,
            model=response.model,
            finish_reason=response.stop_reason or "end_turn",
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
        """Gera chunks de resposta em streaming via eventos Anthropic."""
        import json

        system_text, anthropic_messages = self._convert_messages(messages, system_prompt)
        kwargs = self._build_request_kwargs(
            system_text, anthropic_messages, tools, temperature
        )

        usage: Optional[UsageStats] = None
        finish_reason: str = "end_turn"
        model_name: str = self.model

        # Buffer para tool calls parciais
        current_tool_id: str = ""
        current_tool_name: str = ""
        current_tool_args: str = ""
        in_tool_block: bool = False
        in_thinking_block: bool = False

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    event: MessageStreamEvent

                    # Início da mensagem — captura modelo
                    if isinstance(event, MessageStartEvent):
                        model_name = event.message.model
                        continue

                    # Delta de conteúdo
                    if isinstance(event, ContentBlockDeltaEvent):
                        delta = event.delta

                        if delta.type == "thinking_delta":
                            yield StreamChunk(thinking=delta.thinking)
                            continue

                        if delta.type == "text_delta":
                            yield StreamChunk(content=delta.text)
                            continue

                        if delta.type == "input_json_delta":
                            # Acumula argumentos de tool call
                            current_tool_args += delta.partial_json
                            continue

                    # Início de bloco de conteúdo
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            in_tool_block = True
                            current_tool_id = block.id
                            current_tool_name = block.name
                            current_tool_args = ""
                        elif block.type == "thinking":
                            in_thinking_block = True
                        continue

                    # Fim de bloco de conteúdo
                    if event.type == "content_block_stop":
                        if in_tool_block and current_tool_name:
                            yield StreamChunk(
                                tool_call_delta=ToolCall(
                                    id=current_tool_id,
                                    function=ToolCallFunction(
                                        name=current_tool_name,
                                        arguments=current_tool_args,
                                    ),
                                )
                            )
                            in_tool_block = False
                            current_tool_id = ""
                            current_tool_name = ""
                            current_tool_args = ""
                        in_thinking_block = False
                        continue

                    # Delta de mensagem (stop_reason, usage)
                    if isinstance(event, MessageDeltaEvent):
                        if event.delta.stop_reason:
                            finish_reason = event.delta.stop_reason
                        if event.usage:
                            usage = UsageStats(
                                prompt_tokens=0,
                                completion_tokens=event.usage.output_tokens,
                                total_tokens=event.usage.output_tokens,
                            )
                        continue

        except APIConnectionError as exc:
            raise ConnectionError(
                f"Conexão perdida durante streaming Anthropic: {exc}"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout durante streaming Anthropic (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"Erro da API Anthropic durante streaming [{exc.status_code}]: {exc.message}"
            ) from exc

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
        """
        Lista modelos Anthropic disponíveis.
        A API Anthropic não tem endpoint de listagem — usa lista local.
        """
        return _ANTHROPIC_MODELS

    # ------------------------------------------------------------------
    # health_check()
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verifica conectividade e validade da API key Anthropic."""
        try:
            await self._client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except APIStatusError as exc:
            if exc.status_code == 401:
                logger.error("API key Anthropic inválida ou expirada.")
            elif exc.status_code == 529:
                logger.warning("API Anthropic sobrecarregada (overloaded).")
                return True  # API acessível, apenas congestionada
            else:
                logger.error("Erro de status Anthropic: %s", exc.status_code)
            return False
        except Exception as exc:
            logger.error("Health check Anthropic falhou: %s", exc)
            return False

    def estimate_cost(self, usage: UsageStats) -> float:
        """Calcula custo estimado em USD para Claude 3.5 Sonnet."""
        input_cost = (usage.prompt_tokens / 1_000_000) * _PRICE_INPUT_PER_M
        output_cost = (usage.completion_tokens / 1_000_000) * _PRICE_OUTPUT_PER_M
        return round(input_cost + output_cost, 6)
