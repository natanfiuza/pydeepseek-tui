import json
from enum import Enum
from typing import AsyncGenerator, Callable, Awaitable, List, Dict, Any
from pydeepseek_tui.config.debug_logger import DebugLogger
from pydeepseek_tui.providers.base import BaseAIProvider
from pydeepseek_tui.tools.registry import ToolRegistry
from pydeepseek_tui.tools.base import BaseTool

MAX_HISTORY_MESSAGES = 50


class AgentMode(str, Enum):
    PLAN = "plan"
    AGENT = "agent"
    YOLO = "yolo"


ConfirmCallback = Callable[[str, str], Awaitable[bool]]


class Agent:

    def __init__(
        self,
        provider: BaseAIProvider,
        registry: ToolRegistry,
        mode: AgentMode = AgentMode.AGENT,
        on_confirm: ConfirmCallback | None = None,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.mode = mode
        self.on_confirm = on_confirm
        self.conversation_history: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Voce e o assistente virtual do PyDeepSeek TUI, um assistente "
                    "de IA prestativo, focado em ajudar com programacao, pesquisas "
                    "e tarefas do dia a dia. Voce possui ferramentas para: ler "
                    "arquivos locais, escrever/criar arquivos, executar comandos "
                    "shell, listar diretorios, pesquisar em arquivos, operacoes git, "
                    "buscar informacoes na internet e extrair texto de URLs. "
                    "Sempre use essas ferramentas ativamente para responder com "
                    "precisao. Seja direto, responda em Portugues do Brasil e "
                    "use Markdown para formatar codigos."
                ),
            }
        ]
        self._history_was_trimmed = False

    def _trim_history(self) -> bool:
        if len(self.conversation_history) <= MAX_HISTORY_MESSAGES:
            return False
        system_msg = self.conversation_history[0]
        overflow = len(self.conversation_history) - MAX_HISTORY_MESSAGES + 1
        self.conversation_history = [
            system_msg
        ] + self.conversation_history[overflow + 1:]
        return True

    def _is_destructive(self, tool_name: str) -> bool:
        try:
            tool = self.registry.get_tool(tool_name)
            return getattr(tool, "is_destructive", False)
        except KeyError:
            return False

    async def _check_confirmation(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Verifica se a ferramenta pode ser executada no modo atual."""
        if not self._is_destructive(tool_name):
            return True

        if self.mode == AgentMode.PLAN:
            return False

        if self.mode == AgentMode.AGENT:
            if self.on_confirm:
                return await self.on_confirm(tool_name, json.dumps(args))
            return False

        # YOLO: executa sem confirmar
        return True

    async def chat_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        debug = DebugLogger.get_instance()
        if debug:
            debug.log_user_input(prompt)

        self.conversation_history.append({"role": "user", "content": prompt})
        tools_schema = self.registry.get_api_schema()

        while True:
            tool_calls_buffer: Dict[int, Dict[str, Any]] = {}

            if debug:
                debug.log_prompt(
                    self.conversation_history,
                    tools_schema if tools_schema else None,
                )

            async for chunk in self.provider.stream(
                self.conversation_history, tools=tools_schema
            ):
                if chunk.content:
                    yield chunk.content

                if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                    if debug:
                        debug.log_reasoning(chunk.reasoning_content)

                if chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": "",
                            }
                        if tc.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tc.function.arguments

            if not tool_calls_buffer:
                break

            formatted_calls = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": call["arguments"],
                    },
                }
                for call in tool_calls_buffer.values()
            ]
            self.conversation_history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": formatted_calls,
            })

            for call in tool_calls_buffer.values():
                tool_name = call["name"]

                try:
                    args = json.loads(call["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}

                if not await self._check_confirmation(tool_name, args):
                    result = (
                        f"Bloqueado pelo modo '{self.mode.value}': "
                        f"a ferramenta '{tool_name}' e destrutiva."
                    )
                    if self.mode == AgentMode.PLAN:
                        result += (
                            " O modo plan permite apenas ferramentas de leitura."
                        )
                    elif self.mode == AgentMode.AGENT:
                        result += (
                            " Confirma que desejas executar esta acao."
                        )
                    yield (
                        f"\n\n[bold yellow]Bloqueado {tool_name}:[/bold yellow] "
                        f"{result}\n"
                    )
                else:
                    yield (
                        f"\n\n[bold yellow]A executar {tool_name}..."
                        "[/bold yellow]\n"
                    )

                    try:
                        tool = self.registry.get_tool(tool_name)
                        result = await tool.execute(**args)
                    except Exception as e:
                        result = f"Erro na ferramenta {tool_name}: {str(e)}"

                if debug:
                    debug.log_tool_call(tool_name, json.dumps(args), result)
                    debug.log_tool_result(tool_name, result)

                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": tool_name,
                    "content": result,
                })

            if self._trim_history() and not self._history_was_trimmed:
                self._history_was_trimmed = True
                yield (
                    "\n[dim]Nota: O historico da conversa foi truncado "
                    "para manter o desempenho.[/dim]\n"
                )
