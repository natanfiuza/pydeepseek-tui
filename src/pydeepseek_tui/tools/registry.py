"""
tools/registry.py
=================

ToolRegistry — registro central de todas as tools disponíveis.

Responsabilidades:
  - Registrar e indexar tools por nome
  - Gerar a lista de schemas OpenAI para envio ao modelo
  - Despachar execuções pelo nome da tool
  - Aplicar restrições de modo (plan/agent/yolo)
  - Fornecer listagem para exibição na TUI

Uso:
    from pydeepseek_tui.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register_defaults()

    # Gera schemas para envio ao modelo
    schemas = registry.get_schemas()

    # Executa uma tool pelo nome
    result = await registry.execute("read_file", path="/tmp/test.txt")

    # Lista todas as tools
    for tool in registry.list_tools():
        print(tool.name, tool.is_destructive)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydeepseek_tui.config.settings import AgentMode
from pydeepseek_tui.tools.base import BaseTool, ToolCategory, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registro central e dispatcher de tools.

    O AgentLoop mantém uma instância única do ToolRegistry
    e o usa para todas as interações com tools.
    """

    def __init__(self, agent_mode: AgentMode = AgentMode.AGENT) -> None:
        self._tools: dict[str, BaseTool] = {}
        self.agent_mode = agent_mode

        # Callback chamado antes de executar tools destrutivas no modo 'agent'
        # Assinatura: async (tool: BaseTool, kwargs: dict) -> bool
        # Retorna True para confirmar, False para cancelar
        self.confirmation_callback: Optional[Any] = None

    # ------------------------------------------------------------------
    # Registro de tools
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """
        Registra uma tool no registry.

        Args:
            tool: Instância de BaseTool a registrar.

        Raises:
            ValueError: Se já existir uma tool com o mesmo nome.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' já está registrada. "
                f"Use unregister() antes de registrar novamente."
            )
        if not tool.name:
            raise ValueError("Tool deve ter um 'name' não vazio.")

        self._tools[tool.name] = tool
        logger.debug("Tool registrada: '%s' (destrutiva=%s)", tool.name, tool.is_destructive)

    def unregister(self, name: str) -> None:
        """Remove uma tool do registry pelo nome."""
        self._tools.pop(name, None)

    def register_defaults(self) -> None:
        """
        Registra todas as tools padrão do pydeepseek-tui.

        Importação lazy para evitar dependências circulares e
        permitir que o registro seja feito apenas quando necessário.
        """
        from pydeepseek_tui.tools.fetch_url import FetchUrlTool
        from pydeepseek_tui.tools.git_tool import GitTool
        from pydeepseek_tui.tools.list_dir import ListDirTool
        from pydeepseek_tui.tools.read_file import ReadFileTool
        from pydeepseek_tui.tools.search_files import SearchFilesTool
        from pydeepseek_tui.tools.shell import ShellTool
        from pydeepseek_tui.tools.web_search import WebSearchTool
        from pydeepseek_tui.tools.write_file import WriteFileTool

        default_tools: list[BaseTool] = [
            ReadFileTool(),
            WriteFileTool(),
            ListDirTool(),
            SearchFilesTool(),
            ShellTool(),
            GitTool(),
            WebSearchTool(),
            FetchUrlTool(),
        ]

        for tool in default_tools:
            self.register(tool)

        logger.info(
            "%d tools registradas: %s",
            len(default_tools),
            ", ".join(t.name for t in default_tools),
        )

    # ------------------------------------------------------------------
    # Schemas para o modelo
    # ------------------------------------------------------------------

    def get_schemas(
        self,
        categories: Optional[list[ToolCategory]] = None,
        exclude_destructive: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Gera a lista de schemas OpenAI function calling para envio ao modelo.

        Args:
            categories: Se informado, filtra apenas tools das categorias dadas.
            exclude_destructive: Se True, exclui tools destrutivas (usado no modo plan).

        Returns:
            Lista de dicts no formato OpenAI tools.
        """
        schemas: list[dict[str, Any]] = []

        for tool in self._tools.values():
            if categories and tool.category not in categories:
                continue
            if exclude_destructive and tool.is_destructive:
                continue
            schemas.append(tool.to_openai_schema())

        return schemas

    def get_schemas_for_mode(self) -> list[dict[str, Any]]:
        """
        Retorna os schemas respeitando o modo de operação atual.

        - plan  : exclui tools destrutivas
        - agent : inclui todas (confirmação ocorre na execução)
        - yolo  : inclui todas (sem confirmação)
        """
        if self.agent_mode == AgentMode.PLAN:
            return self.get_schemas(exclude_destructive=True)
        return self.get_schemas()

    # ------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------

    async def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """
        Executa uma tool pelo nome, respeitando o modo de operação.

        Fluxo:
          1. Verifica se a tool existe
          2. Se destrutiva + modo plan → BLOCKED
          3. Se destrutiva + modo agent → pede confirmação via callback
          4. Executa a tool
          5. Retorna ToolResult

        Args:
            tool_name: Nome da tool a executar.
            **kwargs: Argumentos da tool (conforme JSON Schema).

        Returns:
            ToolResult com o resultado da execução.
        """
        tool = self._tools.get(tool_name)

        if tool is None:
            logger.warning("Tool '%s' não encontrada no registry.", tool_name)
            return ToolResult.error(
                error=f"Tool '{tool_name}' não encontrada.",
                output=f"Tools disponíveis: {', '.join(self._tools.keys())}",
            )

        # Modo plan — bloqueia tools destrutivas
        if self.agent_mode == AgentMode.PLAN and tool.is_destructive:
            logger.info(
                "Tool '%s' bloqueada (modo plan não permite ações destrutivas).",
                tool_name,
            )
            return ToolResult.blocked(
                f"Tool '{tool_name}' é destrutiva e está bloqueada no modo 'plan'. "
                f"Mude para o modo 'agent' ou 'yolo' para executar esta ação."
            )

        # Modo agent — pede confirmação para tools destrutivas
        if self.agent_mode == AgentMode.AGENT and tool.is_destructive:
            confirmed = await self._request_confirmation(tool, kwargs)
            if not confirmed:
                logger.info("Execução de '%s' cancelada pelo usuário.", tool_name)
                return ToolResult.cancelled()

        # Executa a tool
        logger.info(
            "Executando tool '%s' com args: %s",
            tool_name,
            self._safe_log_kwargs(kwargs),
        )

        try:
            result = await tool.execute(**kwargs)
            logger.debug(
                "Tool '%s' finalizada com status '%s'.",
                tool_name,
                result.status.value,
            )
            return result

        except TypeError as exc:
            # Argumentos inválidos fornecidos pelo modelo
            logger.error("Argumentos inválidos para '%s': %s", tool_name, exc)
            return ToolResult.error(
                error=f"Argumentos inválidos: {exc}",
                output="O modelo forneceu argumentos incompatíveis com a tool.",
            )
        except Exception as exc:
            logger.exception("Erro inesperado na tool '%s': %s", tool_name, exc)
            return ToolResult.error(
                error=f"Erro inesperado: {type(exc).__name__}: {exc}",
                output="Ocorreu um erro interno na execução da tool.",
            )

    async def execute_from_json(self, tool_name: str, arguments_json: str) -> ToolResult:
        """
        Executa uma tool a partir de argumentos em JSON string.

        Usado diretamente pelo AgentLoop ao receber ToolCall do modelo.

        Args:
            tool_name: Nome da tool.
            arguments_json: Argumentos como JSON string (ex: '{"path": "/tmp/test.txt"}')

        Returns:
            ToolResult com o resultado da execução.
        """
        try:
            kwargs = json.loads(arguments_json) if arguments_json.strip() else {}
        except json.JSONDecodeError as exc:
            logger.error(
                "JSON inválido nos argumentos da tool '%s': %s\nJSON: %s",
                tool_name,
                exc,
                arguments_json,
            )
            return ToolResult.error(
                error=f"Argumentos JSON inválidos: {exc}",
                output=f"O modelo gerou JSON malformado: {arguments_json[:200]}",
            )

        return await self.execute(tool_name, **kwargs)

    # ------------------------------------------------------------------
    # Listagem e consulta
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[BaseTool]:
        """Retorna uma tool pelo nome ou None se não existir."""
        return self._tools.get(name)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        only_destructive: bool = False,
    ) -> list[BaseTool]:
        """
        Lista tools registradas com filtros opcionais.

        Args:
            category: Filtra por categoria.
            only_destructive: Se True, retorna apenas tools destrutivas.

        Returns:
            Lista de BaseTool ordenada por nome.
        """
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]
        if only_destructive:
            tools = [t for t in tools if t.is_destructive]

        return sorted(tools, key=lambda t: t.name)

    def list_by_category(self) -> dict[ToolCategory, list[BaseTool]]:
        """
        Retorna tools agrupadas por categoria.

        Útil para exibição na tela de ajuda da TUI.

        Returns:
            Dict mapeando ToolCategory → lista de tools.
        """
        grouped: dict[ToolCategory, list[BaseTool]] = {}

        for tool in sorted(self._tools.values(), key=lambda t: t.name):
            cat = tool.category
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(tool)

        return grouped

    @property
    def count(self) -> int:
        """Total de tools registradas."""
        return len(self._tools)

    @property
    def names(self) -> list[str]:
        """Lista de nomes de todas as tools registradas."""
        return sorted(self._tools.keys())

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    async def _request_confirmation(
        self, tool: BaseTool, kwargs: dict[str, Any]
    ) -> bool:
        """
        Solicita confirmação ao usuário antes de executar uma tool destrutiva.

        Se o callback não estiver configurado (ex: em testes),
        retorna True por padrão (executa).

        Args:
            tool: Tool a ser confirmada.
            kwargs: Argumentos da execução.

        Returns:
            True para confirmar, False para cancelar.
        """
        if self.confirmation_callback is None:
            logger.warning(
                "confirmation_callback não configurado — executando '%s' sem confirmação.",
                tool.name,
            )
            return True

        try:
            return bool(await self.confirmation_callback(tool, kwargs))
        except Exception as exc:
            logger.error("Erro no confirmation_callback: %s", exc)
            return False

    @staticmethod
    def _safe_log_kwargs(kwargs: dict[str, Any]) -> str:
        """
        Serializa kwargs para log, truncando valores longos.
        Evita vazar conteúdo de arquivos grandes nos logs.
        """
        safe: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, str) and len(v) > 100:
                safe[k] = f"{v[:97]}..."
            else:
                safe[k] = v
        return str(safe)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.names}, mode={self.agent_mode.value!r})"
