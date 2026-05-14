"""
providers/ollama.py
===================

Provider Ollama — modelos de IA rodando localmente.

Ollama expõe uma API REST compatível com OpenAI Chat Completions,
permitindo usar o mesmo SDK sem modificações. Não requer API key.

Instale o Ollama em: https://ollama.com
Modelos populares:
  ollama pull llama3.2
  ollama pull qwen2.5-coder
  ollama pull deepseek-r1
  ollama pull mistral
  ollama pull codellama

Documentação da API Ollama:
  https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

import httpx
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError
from openai.types.chat import ChatCompletionChunk

from pydeepseek_tui.providers.base import (
    BaseProvider,
    ChatResponse,
    Message,
    ModelInfo,
    StreamChunk,
    ToolCall,
    ToolCallFunction,
    UsageStats,
)

logger = logging.getLogger(__name__)

# Modelos Ollama populares (referência local — atualizado via list_models())
_OLLAMA_KNOWN_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="llama3.2",
        name="Llama 3.2",
        context_window=131_072,
        supports_tools=True,
        supports_thinking=False,
        description="Meta Llama 3.2 — excelente para chat e coding geral",
    ),
    ModelInfo(
        id="llama3.2:1b",
        name="Llama 3.2 1B",
        context_window=131_072,
        supports_tools=False,
        supports_thinking=False,
        description="Versão ultra leve do Llama 3.2",
    ),
    ModelInfo(
        id="qwen2.5-coder",
        name="Qwen 2.5 Coder",
        context_window=131_072,
        supports_tools=True,
        supports_thinking=False,
        description="Especializado em geração e revisão de código",
    ),
    ModelInfo(
        id="deepseek-r1",
        name="DeepSeek R1 (local)",
        context_window=65_536,
        supports_tools=False,
        supports_thinking=True,
        description="DeepSeek R1 rodando localmente via Ollama",
    ),
    ModelInfo(
        id="mistral",
        name="Mistral 7B",
        context_window=32_768,
        supports_tools=True,
        supports_thinking=False,
        description="Mistral 7B — rápido e eficiente",
    ),
    ModelInfo(
        id="codellama",
        name="Code Llama",
        context_window=16_384,
        supports_tools=False,
        supports_thinking=False,
        description="Meta Code Llama — especializado em código",
    ),
    ModelInfo(
        id="phi4",
        name="Phi-4",
        context_window=16_384,
        supports_tools=True,
        supports_thinking=False,
        description="Microsoft Phi-4 — compacto e capaz",
    ),
    ModelInfo(
        id="gemma3",
        name="Gemma 3",
        context_window=131_072,
        supports_tools=True,
        supports_thinking=False,
        description="Google Gemma 3 — multimodal e eficiente",
    ),
]


class OllamaProvider(BaseProvider):
    """
    Provider para modelos locais via Ollama.

    Usa o AsyncOpenAI SDK apontando para o endpoint local do Ollama
    (http://localhost:11434/v1), que é compatível com OpenAI Chat Completions.

    Não requer API key — usa "ollama" como placeholder.

    Exemplo:
        provider = OllamaProvider(model="llama3.2")
        async for chunk in provider.stream(messages):
            print(chunk.content, end="")
    """

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        api_key: str = "ollama",          # Placeholder — Ollama não usa API key
        model: str = "llama3.2",
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 300,               # Modelos locais podem ser mais lentos
        max_tokens: int = 8192,
    ) -> None:
        super().__init__(
            api_key=api_key or "ollama",
            model=model,
            base_url=base_url or self.DEFAULT_BASE_URL,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        # Ollama OpenAI-compatible endpoint está em /v1
        openai_base = self.base_url.rstrip("/") + "/v1"

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=openai_base,
            timeout=float(self.timeout),
        )
        # Client httpx direto para chamadas nativas da API Ollama (list models)
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10.0,
        )

    @property
    def provider_name(self) -> str:
        return "Ollama (local)"

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
        """Envia mensagens ao modelo local e aguarda resposta completa."""
        api_messages = self._build_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        # Nem todos os modelos Ollama suportam tools
        if tools and self._model_supports_tools():
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except APIConnectionError as exc:
            raise ConnectionError(
                f"Não foi possível conectar ao Ollama em '{self.base_url}'. "
                f"Verifique se o Ollama está rodando: ollama serve"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout ao aguardar resposta do Ollama (>{self.timeout}s). "
                f"Considere um modelo menor ou aumente REQUEST_TIMEOUT."
            ) from exc
        except APIStatusError as exc:
            if exc.status_code == 404:
                raise RuntimeError(
                    f"Modelo '{self.model}' não encontrado no Ollama. "
                    f"Execute: ollama pull {self.model}"
                ) from exc
            raise RuntimeError(
                f"Erro do Ollama [{exc.status_code}]: {exc.message}"
            ) from exc

        choice = response.choices[0]
        msg = choice.message

        # Thinking mode — DeepSeek-R1 via Ollama retorna <think>...</think> no conteúdo
        content, thinking = self._extract_thinking(msg.content or "")

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

        # Usage (Ollama pode não retornar todos os campos)
        usage = UsageStats()
        if response.usage:
            usage.prompt_tokens = response.usage.prompt_tokens or 0
            usage.completion_tokens = response.usage.completion_tokens or 0
            usage.total_tokens = response.usage.total_tokens or 0

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            thinking=thinking,
            usage=usage,
            model=response.model or self.model,
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
        """Gera chunks de resposta em streaming do modelo local."""
        api_messages = self._build_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if tools and self._model_supports_tools():
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        tool_calls_buffer: dict[int, dict[str, Any]] = {}
        finish_reason: str = "stop"
        usage: Optional[UsageStats] = None
        model_name: str = self.model

        # Buffer para detectar tags <think>...</think> no stream
        thinking_buffer: str = ""
        content_buffer: str = ""
        in_thinking: bool = False

        try:
            async with await self._client.chat.completions.create(**kwargs) as stream:
                async for raw_chunk in stream:
                    raw_chunk: ChatCompletionChunk

                    if not raw_chunk.choices:
                        if raw_chunk.usage:
                            u = raw_chunk.usage
                            usage = UsageStats(
                                prompt_tokens=u.prompt_tokens or 0,
                                completion_tokens=u.completion_tokens or 0,
                                total_tokens=u.total_tokens or 0,
                            )
                        continue

                    choice = raw_chunk.choices[0]
                    delta = choice.delta
                    model_name = raw_chunk.model or self.model

                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

                    # Conteúdo de texto (pode conter <think> do DeepSeek-R1)
                    if delta.content:
                        text = delta.content

                        # Detecta início de bloco <think>
                        if "<think>" in text and not in_thinking:
                            parts = text.split("<think>", 1)
                            if parts[0]:
                                yield StreamChunk(content=parts[0])
                            thinking_buffer = parts[1] if len(parts) > 1 else ""
                            in_thinking = True
                            continue

                        # Detecta fim de bloco </think>
                        if "</think>" in text and in_thinking:
                            parts = text.split("</think>", 1)
                            thinking_buffer += parts[0]
                            yield StreamChunk(thinking=thinking_buffer)
                            thinking_buffer = ""
                            in_thinking = False
                            if len(parts) > 1 and parts[1]:
                                yield StreamChunk(content=parts[1])
                            continue

                        # Dentro do bloco thinking
                        if in_thinking:
                            thinking_buffer += text
                            yield StreamChunk(thinking=text)
                            continue

                        # Conteúdo normal
                        yield StreamChunk(content=text)
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
                f"Ollama não está acessível em '{self.base_url}'. "
                f"Execute: ollama serve"
            ) from exc
        except APITimeoutError as exc:
            raise TimeoutError(
                f"Timeout no streaming do Ollama (>{self.timeout}s)"
            ) from exc
        except APIStatusError as exc:
            if exc.status_code == 404:
                raise RuntimeError(
                    f"Modelo '{self.model}' não encontrado. Execute: ollama pull {self.model}"
                ) from exc
            raise RuntimeError(
                f"Erro do Ollama durante streaming [{exc.status_code}]: {exc.message}"
            ) from exc

        # Emite tool calls completos
        for buf in tool_calls_buffer.values():
            if buf["name"]:
                yield StreamChunk(
                    tool_call_delta=ToolCall(
                        id=buf["id"] or f"call_{buf['name']}",
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
    # list_models() — usa API nativa do Ollama
    # ------------------------------------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        """
        Lista os modelos instalados localmente via API nativa do Ollama.
        Endpoint: GET /api/tags
        """
        try:
            response = await self._http.get("/api/tags")
            response.raise_for_status()
            data = response.json()

            models: list[ModelInfo] = []
            known_ids = {m.id for m in _OLLAMA_KNOWN_MODELS}

            for model_data in data.get("models", []):
                model_id = model_data.get("name", "")
                if not model_id:
                    continue

                # Tenta encontrar metadados locais
                base_id = model_id.split(":")[0]
                known = next(
                    (m for m in _OLLAMA_KNOWN_MODELS if m.id == base_id or m.id == model_id),
                    None,
                )

                size_bytes = model_data.get("size", 0)
                size_gb = round(size_bytes / (1024**3), 1) if size_bytes else 0
                desc = f"{size_gb}GB" if size_gb else "Modelo local"

                models.append(
                    ModelInfo(
                        id=model_id,
                        name=known.name if known else model_id,
                        context_window=known.context_window if known else 32_768,
                        supports_tools=known.supports_tools if known else False,
                        supports_thinking=known.supports_thinking if known else False,
                        description=desc,
                    )
                )

            return sorted(models, key=lambda m: m.id)

        except httpx.ConnectError:
            logger.warning(
                "Ollama não está rodando em '%s'. "
                "Execute 'ollama serve' para iniciá-lo.",
                self.base_url,
            )
            return []
        except Exception as exc:
            logger.warning("Erro ao listar modelos Ollama: %s", exc)
            return _OLLAMA_KNOWN_MODELS

    # ------------------------------------------------------------------
    # health_check()
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verifica se o servidor Ollama está rodando."""
        try:
            response = await self._http.get("/api/version")
            response.raise_for_status()
            version = response.json().get("version", "desconhecida")
            logger.info("Ollama v%s disponível em %s", version, self.base_url)
            return True
        except httpx.ConnectError:
            logger.error(
                "Ollama não está rodando em '%s'. Execute: ollama serve",
                self.base_url,
            )
            return False
        except Exception as exc:
            logger.error("Health check Ollama falhou: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _model_supports_tools(self) -> bool:
        """Verifica se o modelo atual tem suporte a function calling."""
        base_id = self.model.split(":")[0]
        known = next(
            (m for m in _OLLAMA_KNOWN_MODELS if m.id == base_id),
            None,
        )
        # Se não conhecemos o modelo, assume suporte (tentativa otimista)
        return known.supports_tools if known else True

    @staticmethod
    def _extract_thinking(content: str) -> tuple[str, Optional[str]]:
        """
        Extrai blocos <think>...</think> do conteúdo de modelos como DeepSeek-R1.

        Args:
            content: Conteúdo bruto retornado pelo modelo.

        Returns:
            Tupla (conteúdo_limpo, thinking_ou_None)
        """
        if "<think>" not in content:
            return content, None

        thinking_parts: list[str] = []
        clean_parts: list[str] = []
        remaining = content

        while "<think>" in remaining:
            before, rest = remaining.split("<think>", 1)
            if before.strip():
                clean_parts.append(before)
            if "</think>" in rest:
                think_content, remaining = rest.split("</think>", 1)
                thinking_parts.append(think_content.strip())
            else:
                thinking_parts.append(rest.strip())
                remaining = ""
                break

        if remaining.strip():
            clean_parts.append(remaining)

        clean_content = "".join(clean_parts).strip()
        thinking = "\n\n".join(thinking_parts) if thinking_parts else None

        return clean_content, thinking

    def estimate_cost(self, usage: UsageStats) -> float:
        """Ollama é gratuito (roda localmente). Custo sempre zero."""
        return 0.0
