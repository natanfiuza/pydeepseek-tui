import pytest
from pydeepseek_tui.tools.registry import ToolRegistry
from pydeepseek_tui.tools.base import BaseTool
from typing import Any, Dict


class FakeTool(BaseTool):
    @property
    def name(self) -> str:
        return "fake"

    @property
    def description(self) -> str:
        return "Uma ferramenta falsa para testes"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        return "ok"


class AnotherTool(BaseTool):
    @property
    def name(self) -> str:
        return "another"

    @property
    def description(self) -> str:
        return "Outra ferramenta"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        }

    async def execute(self, **kwargs: Any) -> str:
        return kwargs.get("x", "")


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = FakeTool()
        registry.register(tool)
        assert registry.get_tool("fake") is tool

    def test_register_duplicate_raises(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        with pytest.raises(ValueError, match="registrada"):
            registry.register(FakeTool())

    def test_get_missing_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="nao_existe"):
            registry.get_tool("nao_existe")

    def test_get_api_schema_empty(self):
        registry = ToolRegistry()
        assert registry.get_api_schema() == []

    def test_get_api_schema_format(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        registry.register(AnotherTool())

        schema = registry.get_api_schema()
        assert len(schema) == 2

        for item in schema:
            assert item["type"] == "function"
            assert "name" in item["function"]
            assert "description" in item["function"]
            assert "parameters" in item["function"]

    def test_get_api_schema_contains_names(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        registry.register(AnotherTool())

        names = [item["function"]["name"] for item in registry.get_api_schema()]
        assert "fake" in names
        assert "another" in names
