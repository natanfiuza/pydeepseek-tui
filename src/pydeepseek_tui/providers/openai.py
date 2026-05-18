import os
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI

from pydeepseek_tui.providers.base import BaseAIProvider, UsageInfo


class OpenAIProvider(BaseAIProvider):

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "A chave da API da OpenAI nao foi encontrada. "
                "Define OPENAI_API_KEY no ambiente."
            )

        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.last_usage: UsageInfo | None = None

    async def ask(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> AsyncGenerator[Any, None]:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        self.last_usage = None
        stream_response = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream_response:
            if hasattr(chunk, "usage") and chunk.usage is not None:
                reasoning = 0
                details = getattr(chunk.usage, "completion_tokens_details", None)
                if details is not None:
                    reasoning = getattr(details, "reasoning_tokens", 0) or 0
                self.last_usage = UsageInfo(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                    reasoning_tokens=reasoning,
                )
            yield chunk.choices[0].delta

    async def close(self) -> None:
        await self.client.close()
