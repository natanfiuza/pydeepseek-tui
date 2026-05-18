import os
from typing import AsyncGenerator, List, Dict, Any
from anthropic import AsyncAnthropic

from pydeepseek_tui.providers.base import BaseAIProvider, UsageInfo


class AnthropicDelta:
    """Adapta o delta de streaming da Anthropic para formato compativel
    com o Agent (que espera o formato OpenAI: .content e .tool_calls)."""

    def __init__(
        self,
        content: str | None = None,
        tool_calls: Any = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls


class AnthropicToolCall:
    """Wrapper para tool calls no formato esperado pelo Agent."""

    def __init__(self, index: int, call_id: str, name: str, arguments: str):
        self.index = index
        self.id = call_id
        self.function = _AnthropicFunction(name, arguments)


class _AnthropicFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class AnthropicProvider(BaseAIProvider):

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "A chave da API da Anthropic nao foi encontrada. "
                "Define ANTHROPIC_API_KEY no ambiente."
            )

        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.last_usage: UsageInfo | None = None

    def _messages_to_anthropic(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[str | None, List[Dict[str, Any]]]:
        """Extrai system message e converte para formato Anthropic."""
        system = None
        converted = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                system = content
                continue

            if role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": content or "",
                            }
                        ],
                    }
                )
                continue

            if role == "assistant" and msg.get("tool_calls"):
                tool_blocks = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    tool_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": fn.get("name", ""),
                            "input": _parse_json_args(fn.get("arguments", "{}")),
                        }
                    )
                converted.append({"role": "assistant", "content": tool_blocks})
                continue

            if role in ("user", "assistant") and content is not None:
                converted.append({"role": role, "content": content})

        return system, converted

    def _anthropic_tools_schema(
        self, tools: List[Dict[str, Any]] | None
    ) -> List[Dict[str, Any]] | None:
        if not tools:
            return None
        converted = []
        for t in tools:
            fn = t.get("function", {})
            converted.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        return converted

    async def ask(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> Any:
        system, anthropic_msgs = self._messages_to_anthropic(messages)
        anthropic_tools = self._anthropic_tools_schema(tools)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_msgs,
            "max_tokens": 4096,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self.client.messages.create(**kwargs)
        return response

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> AsyncGenerator[Any, None]:
        system, anthropic_msgs = self._messages_to_anthropic(messages)
        anthropic_tools = self._anthropic_tools_schema(tools)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_msgs,
            "max_tokens": 4096,
            "stream": True,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        self.last_usage = None
        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text") and delta.text:
                        yield AnthropicDelta(content=delta.text)
                    elif hasattr(delta, "partial_json"):
                        yield AnthropicDelta(content=delta.partial_json)

                elif event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        yield AnthropicDelta(
                            tool_calls=[
                                AnthropicToolCall(
                                    index=0,
                                    call_id=block.id,
                                    name=block.name,
                                    arguments="",
                                )
                            ]
                        )

                elif event.type == "message_stop":
                    break

        try:
            final = await stream.get_final_message()
            if hasattr(final, "usage") and final.usage is not None:
                self.last_usage = UsageInfo(
                    prompt_tokens=final.usage.input_tokens or 0,
                    completion_tokens=final.usage.output_tokens or 0,
                    total_tokens=(final.usage.input_tokens or 0)
                    + (final.usage.output_tokens or 0),
                    reasoning_tokens=0,
                )
        except Exception:
            self.last_usage = None

    async def close(self) -> None:
        await self.client.close()


def _parse_json_args(args: str) -> Dict[str, Any]:
    import json

    try:
        return json.loads(args)
    except (json.JSONDecodeError, TypeError):
        return {}
