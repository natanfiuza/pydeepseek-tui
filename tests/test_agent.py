import pytest
from typing import AsyncGenerator, List, Dict, Any
from pydeepseek_tui.agent import Agent
from pydeepseek_tui.providers.base import BaseAIProvider
from pydeepseek_tui.tools.base import BaseTool
from pydeepseek_tui.tools.registry import ToolRegistry


class MockToolCall:
    def __init__(self, index: int, id: str, name: str, arguments: str):
        self.index = index
        self.id = id
        self.function = MockFunction(name, arguments)


class MockFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class MockDelta:
    def __init__(self, content: str | None = None, tool_calls: Any = None):
        self.content = content
        self.tool_calls = tool_calls


class MockProvider(BaseAIProvider):
    async def ask(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> Any:
        return "Resposta mockada."

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> AsyncGenerator[Any, None]:
        yield MockDelta(content="Ola, ")
        yield MockDelta(content="sou um teste ")
        yield MockDelta(content="seguro e rapido!")


class MockProviderWithToolCall(BaseAIProvider):
    """Provedor que simula um tool call e depois responde com texto."""

    def __init__(self):
        self._call_count = 0

    async def ask(self, messages, tools=None):
        return "tool mock"

    async def stream(self, messages, tools=None):
        self._call_count += 1
        if self._call_count == 1:
            yield MockDelta(
                tool_calls=[
                    MockToolCall(
                        index=0,
                        id="call_123",
                        name="fake_tool",
                        arguments='{"arg1": "valor"}',
                    )
                ]
            )
        else:
            yield MockDelta(content="Resultado processado pela ferramenta.")


class MockProviderWithToolCallStreaming(BaseAIProvider):
    """Provedor que simula um tool call fragmentado (streaming real)."""

    def __init__(self):
        self._call_count = 0

    async def ask(self, messages, tools=None):
        return "tool streaming mock"

    async def stream(self, messages, tools=None):
        self._call_count += 1
        if self._call_count == 1:
            yield MockDelta(
                tool_calls=[
                    MockToolCall(index=0, id="call_abc", name="fake_tool", arguments=""),
                ]
            )
            yield MockDelta(
                tool_calls=[
                    MockToolCall(index=0, id=None, name=None, arguments='{"x":'),
                ]
            )
            yield MockDelta(
                tool_calls=[
                    MockToolCall(index=0, id=None, name=None, arguments=" 1}"),
                ]
            )
        else:
            yield MockDelta(content="Resultado apos streaming tool call.")


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "Ferramenta falsa para testes"
    parameters = {
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": ["arg1"],
    }

    async def execute(self, **kwargs):
        return f"Resultado: {kwargs}"


@pytest.fixture
def mock_agent():
    registry = ToolRegistry()
    provider = MockProvider()
    return Agent(provider=provider, registry=registry)


@pytest.fixture
def mock_agent_with_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    provider = MockProviderWithToolCall()
    return Agent(provider=provider, registry=registry)


@pytest.fixture
def mock_agent_streaming_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    provider = MockProviderWithToolCallStreaming()
    return Agent(provider=provider, registry=registry)


@pytest.mark.asyncio
async def test_agent_chat_stream_and_history(mock_agent):
    prompt = "Faz um teste para mim!"

    response_chunks = []
    async for chunk in mock_agent.chat_stream(prompt):
        response_chunks.append(chunk)

    full_response = "".join(response_chunks)
    assert full_response == "Ola, sou um teste seguro e rapido!"

    last_user = next(
        m
        for m in reversed(mock_agent.conversation_history)
        if m["role"] == "user"
    )
    assert last_user["content"] == prompt


@pytest.mark.asyncio
async def test_agent_tool_calling(mock_agent_with_tool):
    prompt = "executa a ferramenta fake"

    chunks = []
    async for chunk in mock_agent_with_tool.chat_stream(prompt):
        chunks.append(chunk)

    full = "".join(chunks)
    assert "A executar fake_tool" in full
    assert "Resultado processado" in full

    tool_messages = [
        m for m in mock_agent_with_tool.conversation_history if m["role"] == "tool"
    ]
    assert len(tool_messages) == 1
    assert tool_messages[0]["name"] == "fake_tool"


@pytest.mark.asyncio
async def test_agent_streaming_tool_call_accumulation(mock_agent_streaming_tool):
    prompt = "usa a fake tool"

    chunks = []
    async for chunk in mock_agent_streaming_tool.chat_stream(prompt):
        chunks.append(chunk)

    full = "".join(chunks)
    assert "A executar fake_tool" in full
    assert "Resultado apos streaming" in full


@pytest.mark.asyncio
async def test_agent_history_preserves_system_message(mock_agent):
    assert mock_agent.conversation_history[0]["role"] == "system"
    await mock_agent.chat_stream("teste 1").__anext__()
    assert mock_agent.conversation_history[0]["role"] == "system"


def test_trim_history_preserves_system_message(mock_agent):
    from pydeepseek_tui.agent import MAX_HISTORY_MESSAGES

    for i in range(MAX_HISTORY_MESSAGES + 10):
        mock_agent.conversation_history.append({
            "role": "user",
            "content": f"teste {i}",
        })
        mock_agent.conversation_history.append({
            "role": "assistant",
            "content": f"resposta {i}",
        })

    assert len(mock_agent.conversation_history) > MAX_HISTORY_MESSAGES

    trimmed = mock_agent._trim_history()
    assert trimmed
    assert mock_agent.conversation_history[0]["role"] == "system"
    assert len(mock_agent.conversation_history) <= MAX_HISTORY_MESSAGES


def test_trim_history_no_op_when_under_limit(mock_agent):
    from pydeepseek_tui.agent import MAX_HISTORY_MESSAGES

    assert len(mock_agent.conversation_history) < MAX_HISTORY_MESSAGES
    trimmed = mock_agent._trim_history()
    assert not trimmed
