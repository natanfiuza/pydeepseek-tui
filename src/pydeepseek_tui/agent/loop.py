"""
agent/loop.py
=============

AgentLoop -- Orquestrador principal do ciclo de raciocinio do agente.

Implementa o loop ReAct (Reason + Act):
  1. Envia mensagens + tools ao modelo LLM
  2. Recebe resposta (texto e/ou tool calls)
  3. Executa as tools solicitadas via ToolRegistry
  4. Adiciona resultados ao historico
  5. Repete ate o modelo nao solicitar mais tools (finish_reason=stop)

Suporta:
  - Streaming em tempo real com callbacks
  - Thinking mode (chain-of-thought visivel)
  - Multiplas tool calls em paralelo (quando possivel)
  - Limite de iteracoes para prevenir loops infinitos
  - Modos plan / agent / yolo
  - Injecao de system prompt customizado
  - Historico de sessao persistente

Fluxo detalhado:
    usuario envia mensagem
        └─> AgentLoop.run(message)
                └─> _build_messages()       # monta historico
                └─> provider.stream()       # chama LLM
                        └─> StreamChunk     # thinking / content / tool_call
                └─> _execute_tool_calls()   # executa tools em paralelo
                └─> _add_tool_results()     # injeta resultados no historico
                └─> repete (max_iterations)
                └─> AgentResponse           # retorna ao chamador (TUI)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Optional

from pydeepseek_tui.config.settings import AgentMode, get_settings
from pydeepseek_tui.providers.base import (
    BaseProvider,
    ChatResponse,
    Message,
    MessageRole,
    StreamChunk,
    ToolCall,
    UsageStats,
)
from pydeepseek_tui.tools.base import ToolResult
from pydeepseek_tui.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Maximo de iteracoes tool-call por turno (protege contra loops infinitos)
_MAX_ITERATIONS = 10

# System prompt padrao do agente
_DEFAULT_SYSTEM_PROMPT = """Voce e um agente de IA especializado em desenvolvimento de software.
Voce tem acesso a ferramentas para ler/escrever arquivos, executar comandos shell,
realizar operacoes Git e buscar informacoes na web.

Diretrizes:
- Analise cuidadosamente a solicitacao antes de agir
- Prefira acoes minimamente invasivas (leia antes de escrever)
- Explique o que esta fazendo e por que
- Em caso de duvida, peca confirmacao antes de modificar arquivos importantes
- Seja conciso e objetivo nas respostas
- Use as ferramentas de forma eficiente, evitando chamadas desnecessarias
"""


# ---------------------------------------------------------------------------
# Tipos de dados do AgentLoop
# ---------------------------------------------------------------------------

@dataclass
class ToolCallEvent:
    """Evento emitido quando o agente executa uma tool."""
    tool_name: str
    arguments: dict[str, Any]
    result: ToolResult
    duration_ms: float


@dataclass
class AgentResponse:
    """Resposta completa de um turno do agente."""
    content: str                              # Resposta final em texto
    thinking: Optional[str] = None           # Chain-of-thought (se disponivel)
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    usage: UsageStats = field(default_factory=UsageStats)
    iterations: int = 0                      # Quantas iteracoes tool-call ocorreram
    duration_ms: float = 0.0                 # Tempo total do turno
    model: str = ""
    error: Optional[str] = None             # Erro fatal, se ocorreu

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @property
    def tools_used(self) -> list[str]:
        return [e.tool_name for e in self.tool_calls]


# Tipos de callbacks para a TUI
OnChunkCallback   = Callable[[StreamChunk], None]          # chunk de streaming
OnToolCallCallback = Callable[[str, dict], None]           # antes de executar tool
OnToolResultCallback = Callable[[ToolCallEvent], None]     # apos executar tool
OnIterationCallback = Callable[[int], None]                # inicio de cada iteracao


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------

class AgentLoop:
    """
    Orquestrador do ciclo de raciocinio do agente (ReAct loop).

    Uso basico:
        loop = AgentLoop(provider=provider, registry=registry)
        response = await loop.run("Leia o arquivo main.py e me explique o que ele faz")
        print(response.content)

    Com streaming:
        async for chunk in loop.stream("Corrija o bug na funcao parse()"):
            print(chunk.content, end="", flush=True)
    """

    def __init__(
        self,
        provider: BaseProvider,
        registry: Optional[ToolRegistry] = None,
        agent_mode: AgentMode = AgentMode.AGENT,
        system_prompt: Optional[str] = None,
        max_iterations: int = _MAX_ITERATIONS,
        # Callbacks opcionais para a TUI
        on_chunk: Optional[OnChunkCallback] = None,
        on_tool_call: Optional[OnToolCallCallback] = None,
        on_tool_result: Optional[OnToolResultCallback] = None,
        on_iteration: Optional[OnIterationCallback] = None,
    ) -> None:
        self.provider = provider
        self.agent_mode = agent_mode
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.max_iterations = max_iterations

        # Callbacks
        self.on_chunk = on_chunk
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_iteration = on_iteration

        # Registry de tools
        if registry is None:
            self.registry = ToolRegistry(agent_mode=agent_mode)
            self.registry.register_defaults()
        else:
            self.registry = registry
            self.registry.agent_mode = agent_mode

        # Historico de mensagens da sessao atual
        self._history: list[Message] = []

        # Estatisticas acumuladas da sessao
        self._session_usage = UsageStats()

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    async def run(
        self,
        user_message: str,
        temperature: float = 0.7,
    ) -> AgentResponse:
        """
        Executa um turno completo do agente (sem streaming).

        Adiciona a mensagem do usuario ao historico, chama o LLM,
        executa tools se necessario, e retorna a resposta final.

        Args:
            user_message: Mensagem do usuario.
            temperature:  Temperatura do modelo (0.0 = deterministico).

        Returns:
            AgentResponse com conteudo, thinking, tools usadas e metricas.
        """
        start = time.monotonic()

        # Adiciona mensagem do usuario ao historico
        self._add_user_message(user_message)

        # Acumula chunks internamente (sem streaming externo)
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_events: list[ToolCallEvent] = []
        total_usage = UsageStats()
        model_name = self.provider.model
        iterations = 0

        # Buffer de chunks para processamento interno
        async def _collect_chunk(chunk: StreamChunk) -> None:
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.thinking:
                thinking_parts.append(chunk.thinking)

        # Salva callback original e substitui temporariamente
        original_on_chunk = self.on_chunk
        self.on_chunk = _collect_chunk  # type: ignore

        try:
            # Executa o loop ReAct
            tool_events, total_usage, model_name, iterations, error =                 await self._react_loop(temperature)
        finally:
            self.on_chunk = original_on_chunk

        duration_ms = (time.monotonic() - start) * 1000

        # Ultima mensagem do assistente ja foi adicionada ao historico pelo _react_loop
        # Recupera o conteudo final da ultima mensagem assistant
        final_content = self._get_last_assistant_content()

        self._accumulate_usage(total_usage)

        return AgentResponse(
            content=final_content,
            thinking="

".join(thinking_parts) or None,
            tool_calls=tool_events,
            usage=total_usage,
            iterations=iterations,
            duration_ms=duration_ms,
            model=model_name,
            error=error,
        )

    async def stream(
        self,
        user_message: str,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Executa um turno do agente com streaming de chunks em tempo real.

        Yields StreamChunk para cada fragmento recebido do modelo e
        para cada evento de tool (via metadata no chunk).

        Args:
            user_message: Mensagem do usuario.
            temperature:  Temperatura do modelo.

        Yields:
            StreamChunk com content, thinking, tool_call_delta ou is_final.
        """
        self._add_user_message(user_message)

        chunks_buffer: list[StreamChunk] = []

        async def _capture(chunk: StreamChunk) -> None:
            chunks_buffer.append(chunk)

        original = self.on_chunk
        self.on_chunk = _capture  # type: ignore

        # Executa o loop em background, liberando chunks conforme chegam
        # Usamos uma fila para comunicar chunks entre coroutines
        queue: asyncio.Queue[Optional[StreamChunk]] = asyncio.Queue()

        async def _capture_to_queue(chunk: StreamChunk) -> None:
            await queue.put(chunk)

        self.on_chunk = _capture_to_queue  # type: ignore

        async def _run_loop() -> None:
            try:
                await self._react_loop(temperature)
            finally:
                await queue.put(None)  # Sinal de fim

        loop_task = asyncio.create_task(_run_loop())

        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            self.on_chunk = original
            if not loop_task.done():
                loop_task.cancel()
                try:
                    await loop_task
                except asyncio.CancelledError:
                    pass

    def add_system_context(self, context: str) -> None:
        """
        Injeta contexto adicional no system prompt dinamicamente.
        Util para adicionar informacoes do workspace (arquivos abertos, etc.)
        """
        self.system_prompt = self.system_prompt + f"

{context}"

    def clear_history(self) -> None:
        """Limpa o historico de mensagens da sessao atual."""
        self._history.clear()
        logger.info("Historico da sessao limpo.")

    def get_history(self) -> list[Message]:
        """Retorna copia do historico atual."""
        return list(self._history)

    def load_history(self, messages: list[Message]) -> None:
        """Restaura o historico de uma sessao salva."""
        self._history = list(messages)
        logger.info("Historico restaurado: %d mensagens.", len(messages))

    @property
    def session_usage(self) -> UsageStats:
        """Estatisticas de uso acumuladas na sessao."""
        return self._session_usage

    # ------------------------------------------------------------------
    # ReAct loop interno
    # ------------------------------------------------------------------

    async def _react_loop(
        self,
        temperature: float,
    ) -> tuple[list[ToolCallEvent], UsageStats, str, int, Optional[str]]:
        """
        Loop principal ReAct: LLM → tools → LLM → ... → resposta final.

        Returns:
            (tool_events, total_usage, model_name, iterations, error)
        """
        tool_events: list[ToolCallEvent] = []
        total_usage = UsageStats()
        model_name = self.provider.model
        iterations = 0
        error: Optional[str] = None

        # Schemas das tools para o modelo (respeitando o modo)
        tool_schemas = self.registry.get_schemas_for_mode()

        while iterations < self.max_iterations:
            iterations += 1

            if self.on_iteration:
                if asyncio.iscoroutinefunction(self.on_iteration):
                    await self.on_iteration(iterations)
                else:
                    self.on_iteration(iterations)

            logger.debug("Iteracao %d/%d", iterations, self.max_iterations)

            # Chama o modelo em streaming
            content_buf: list[str] = []
            thinking_buf: list[str] = []
            pending_tool_calls: list[ToolCall] = []
            finish_reason = "stop"
            chunk_usage = UsageStats()

            try:
                async for chunk in await self.provider.stream(
                    messages=self._history,
                    tools=tool_schemas if tool_schemas else None,
                    system_prompt=self.system_prompt,
                    temperature=temperature,
                ):
                    # Repassa chunk para callback externo (TUI)
                    if self.on_chunk:
                        if asyncio.iscoroutinefunction(self.on_chunk):
                            await self.on_chunk(chunk)
                        else:
                            self.on_chunk(chunk)

                    if chunk.content:
                        content_buf.append(chunk.content)
                    if chunk.thinking:
                        thinking_buf.append(chunk.thinking)
                    if chunk.tool_call_delta:
                        pending_tool_calls.append(chunk.tool_call_delta)
                    if chunk.is_final:
                        finish_reason = chunk.finish_reason or "stop"
                        if chunk.usage:
                            chunk_usage = chunk.usage
                        if chunk.model:
                            model_name = chunk.model

            except (ConnectionError, TimeoutError, RuntimeError) as exc:
                error = str(exc)
                logger.error("Erro na chamada ao modelo: %s", exc)
                break

            # Acumula usage
            total_usage.prompt_tokens += chunk_usage.prompt_tokens
            total_usage.completion_tokens += chunk_usage.completion_tokens
            total_usage.total_tokens += chunk_usage.total_tokens

            content = "".join(content_buf)
            thinking = "".join(thinking_buf) or None

            # Adiciona resposta do assistente ao historico
            if content or pending_tool_calls:
                assistant_msg = Message.assistant(
                    content=content or "",
                    tool_calls=pending_tool_calls or None,
                    thinking=thinking,
                )
                self._history.append(assistant_msg)

            # Sem tool calls — resposta final
            if not pending_tool_calls or finish_reason == "stop":
                logger.debug("Resposta final na iteracao %d.", iterations)
                break

            # Executa as tool calls
            logger.info(
                "Executando %d tool(s): %s",
                len(pending_tool_calls),
                [tc.function.name for tc in pending_tool_calls],
            )

            events = await self._execute_tool_calls(pending_tool_calls)
            tool_events.extend(events)

            # Adiciona resultados ao historico
            for event in events:
                self._history.append(
                    Message.tool_result(
                        tool_call_id=next(
                            (tc.id for tc in pending_tool_calls
                             if tc.function.name == event.tool_name),
                            event.tool_name,
                        ),
                        content=event.result.to_model_string(),
                    )
                )

        else:
            logger.warning(
                "Limite de %d iteracoes atingido. Forcando finalizacao.",
                self.max_iterations,
            )
            error = f"Limite de {self.max_iterations} iteracoes atingido."
            # Adiciona aviso ao historico para o modelo saber
            self._history.append(
                Message.assistant(
                    content=(
                        f"[Sistema: limite de {self.max_iterations} chamadas de tools "
                        f"atingido. Resumindo o que foi feito ate aqui.]"
                    )
                )
            )

        return tool_events, total_usage, model_name, iterations, error

    # ------------------------------------------------------------------
    # Execucao de tools
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolCallEvent]:
        """
        Executa multiplas tool calls, em paralelo quando possivel.

        Tools destrutivas sao executadas sequencialmente para seguranca.
        Tools nao-destrutivas sao executadas em paralelo.

        Returns:
            Lista de ToolCallEvent com resultado de cada tool.
        """
        # Separa destrutivas (sequencial) de nao-destrutivas (paralelo)
        destructive: list[ToolCall] = []
        safe: list[ToolCall] = []

        for tc in tool_calls:
            tool = self.registry.get(tc.function.name)
            if tool and tool.is_destructive:
                destructive.append(tc)
            else:
                safe.append(tc)

        events: list[ToolCallEvent] = []

        # Executa nao-destrutivas em paralelo
        if safe:
            tasks = [self._execute_single(tc) for tc in safe]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for tc, result in zip(safe, results):
                if isinstance(result, Exception):
                    events.append(ToolCallEvent(
                        tool_name=tc.function.name,
                        arguments={},
                        result=ToolResult.error(error=str(result)),
                        duration_ms=0.0,
                    ))
                else:
                    events.append(result)

        # Executa destrutivas sequencialmente
        for tc in destructive:
            event = await self._execute_single(tc)
            events.append(event)

        return events

    async def _execute_single(self, tc: ToolCall) -> ToolCallEvent:
        """Executa uma unica tool call e retorna o evento."""
        import json

        tool_name = tc.function.name
        args_json = tc.function.arguments or "{}"

        # Parse dos argumentos
        try:
            arguments = json.loads(args_json) if args_json.strip() else {}
        except json.JSONDecodeError:
            arguments = {}

        # Callback antes da execucao
        if self.on_tool_call:
            if asyncio.iscoroutinefunction(self.on_tool_call):
                await self.on_tool_call(tool_name, arguments)
            else:
                self.on_tool_call(tool_name, arguments)

        start = time.monotonic()
        result = await self.registry.execute_from_json(tool_name, args_json)
        duration_ms = (time.monotonic() - start) * 1000

        event = ToolCallEvent(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )

        # Callback apos a execucao
        if self.on_tool_result:
            if asyncio.iscoroutinefunction(self.on_tool_result):
                await self.on_tool_result(event)
            else:
                self.on_tool_result(event)

        logger.info(
            "Tool '%s' -> %s (%.0fms)",
            tool_name,
            result.status.value,
            duration_ms,
        )

        return event

    # ------------------------------------------------------------------
    # Helpers de historico
    # ------------------------------------------------------------------

    def _add_user_message(self, content: str) -> None:
        self._history.append(Message(role=MessageRole.USER, content=content))

    def _get_last_assistant_content(self) -> str:
        for msg in reversed(self._history):
            if msg.role == MessageRole.ASSISTANT and msg.content:
                return msg.content
        return ""

    def _build_messages(self) -> list[Message]:
        """Retorna o historico atual (sem system prompt, que vai separado)."""
        return [m for m in self._history if m.role != MessageRole.SYSTEM]

    def _accumulate_usage(self, usage: UsageStats) -> None:
        self._session_usage.prompt_tokens += usage.prompt_tokens
        self._session_usage.completion_tokens += usage.completion_tokens
        self._session_usage.total_tokens += usage.total_tokens
