import pytest
from pydeepseek_tui.agent import Agent, AgentMode
from pydeepseek_tui.providers.base import BaseAIProvider
from pydeepseek_tui.tools.registry import ToolRegistry
from pydeepseek_tui.tools.base import BaseTool


class DestructiveTool(BaseTool):
    name = "rm_files"
    description = "Remove arquivos"
    is_destructive = True
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, **kwargs):
        return "Ficheiros removidos."


class ReadOnlyTool(BaseTool):
    name = "list_files"
    description = "Lista arquivos"
    is_destructive = False
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return "lista.txt"


class MockToolCall:
    def __init__(self, index, id, name, arguments):
        self.index = index
        self.id = id
        self.function = MockFunction(name, arguments)


class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class MockDelta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class ModeMockProvider(BaseAIProvider):
    def __init__(self):
        self._call_count = 0

    async def ask(self, messages, tools=None):
        return "mock"

    async def stream(self, messages, tools=None):
        self._call_count += 1
        if self._call_count == 1:
            yield MockDelta(
                tool_calls=[
                    MockToolCall(
                        index=0, id="c1", name="rm_files", arguments='{"path": "/tmp"}'
                    )
                ]
            )
        else:
            yield MockDelta(content="Operacao concluida.")


@pytest.fixture
def mode_registry():
    r = ToolRegistry()
    r.register(DestructiveTool())
    r.register(ReadOnlyTool())
    return r


@pytest.mark.asyncio
async def test_plan_mode_blocks_destructive(mode_registry):
    agent = Agent(
        provider=ModeMockProvider(),
        registry=mode_registry,
        mode=AgentMode.PLAN,
    )
    chunks = []
    async for chunk in agent.chat_stream("remove /tmp"):
        chunks.append(chunk)

    full = "".join(chunks)
    assert "Bloqueado" in full


@pytest.mark.asyncio
async def test_agent_mode_blocks_without_confirm(mode_registry):
    agent = Agent(
        provider=ModeMockProvider(),
        registry=mode_registry,
        mode=AgentMode.AGENT,
    )
    chunks = []
    async for chunk in agent.chat_stream("remove /tmp"):
        chunks.append(chunk)

    full = "".join(chunks)
    assert "Bloqueado" in full


@pytest.mark.asyncio
async def test_agent_mode_allows_with_confirm(mode_registry):
    async def always_confirm(tool_name, args):
        return True

    agent = Agent(
        provider=ModeMockProvider(),
        registry=mode_registry,
        mode=AgentMode.AGENT,
        on_confirm=always_confirm,
    )
    chunks = []
    async for chunk in agent.chat_stream("remove /tmp"):
        chunks.append(chunk)

    full = "".join(chunks)
    assert "A executar rm_files" in full


@pytest.mark.asyncio
async def test_yolo_mode_executes_always(mode_registry):
    agent = Agent(
        provider=ModeMockProvider(),
        registry=mode_registry,
        mode=AgentMode.YOLO,
    )
    chunks = []
    async for chunk in agent.chat_stream("remove /tmp"):
        chunks.append(chunk)

    full = "".join(chunks)
    assert "A executar rm_files" in full
