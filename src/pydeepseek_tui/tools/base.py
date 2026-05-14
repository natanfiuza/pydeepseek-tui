"""
tools/base.py
=============

Interface abstrata e tipos compartilhados para todas as tools do agente.

Cada tool representa uma capacidade do agente:
  - Leitura/escrita de arquivos
  - Execução de comandos shell
  - Operações Git
  - Busca na web
  - etc.

As tools são descritas via JSON Schema (OpenAI function calling format)
e executadas pelo AgentLoop quando o modelo solicita.

Fluxo:
  1. AgentLoop envia as tools para o modelo via tool_schemas
  2. Modelo retorna um ToolCall com nome e argumentos JSON
  3. AgentLoop executa tool.execute(arguments)
  4. Resultado é adicionado ao histórico como Message.tool_result()
  5. Modelo recebe o resultado e continua o raciocínio
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ToolStatus(str, Enum):
    """Status de execução de uma tool."""

    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"       # Tool bloqueada pelo modo de operação (ex: plan)
    CANCELLED = "cancelled"   # Usuário recusou a confirmação (modo agent)
    TIMEOUT = "timeout"       # Execução excedeu o tempo limite


class ToolCategory(str, Enum):
    """Categoria da tool para agrupamento na TUI."""

    FILESYSTEM = "filesystem"   # Leitura e escrita de arquivos
    SHELL = "shell"             # Execução de comandos
    GIT = "git"                 # Operações Git
    SEARCH = "search"           # Busca em arquivos e na web
    NETWORK = "network"         # Requisições HTTP


# ---------------------------------------------------------------------------
# Tipos de dados
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """
    Resultado da execução de uma tool.

    Sempre retornado por tool.execute(), independente de sucesso ou falha.
    O AgentLoop converte este resultado em Message.tool_result() para
    adicionar ao histórico de conversa.
    """

    status: ToolStatus
    output: str                          # Saída principal (para o modelo)
    error: Optional[str] = None          # Mensagem de erro (se status=ERROR)
    metadata: dict[str, Any] = field(default_factory=dict)  # Dados extras para a TUI

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.status in (ToolStatus.ERROR, ToolStatus.TIMEOUT)

    @property
    def is_blocked(self) -> bool:
        return self.status in (ToolStatus.BLOCKED, ToolStatus.CANCELLED)

    def to_model_string(self) -> str:
        """
        Serializa o resultado para string a ser enviada ao modelo.
        Inclui status e erro quando relevante.
        """
        if self.is_success:
            return self.output or "(sem saída)"
        if self.status == ToolStatus.BLOCKED:
            return f"[BLOQUEADO] {self.output}"
        if self.status == ToolStatus.CANCELLED:
            return "[CANCELADO] Usuário recusou a execução desta ação."
        if self.status == ToolStatus.TIMEOUT:
            return f"[TIMEOUT] A execução excedeu o tempo limite.\n{self.error or ''}"
        # ERROR
        return f"[ERRO] {self.error or self.output}"

    @classmethod
    def success(cls, output: str, **metadata: Any) -> "ToolResult":
        """Atalho para resultado bem-sucedido."""
        return cls(status=ToolStatus.SUCCESS, output=output, metadata=metadata)

    @classmethod
    def error(cls, error: str, output: str = "", **metadata: Any) -> "ToolResult":
        """Atalho para resultado de erro."""
        return cls(status=ToolStatus.ERROR, output=output, error=error, metadata=metadata)

    @classmethod
    def blocked(cls, reason: str) -> "ToolResult":
        """Atalho para tool bloqueada pelo modo de operação."""
        return cls(status=ToolStatus.BLOCKED, output=reason)

    @classmethod
    def cancelled(cls) -> "ToolResult":
        """Atalho para execução cancelada pelo usuário."""
        return cls(status=ToolStatus.CANCELLED, output="Execução cancelada pelo usuário.")

    @classmethod
    def timeout(cls, seconds: int) -> "ToolResult":
        """Atalho para timeout de execução."""
        return cls(
            status=ToolStatus.TIMEOUT,
            output=f"Timeout após {seconds}s",
            error=f"A execução excedeu o limite de {seconds} segundos.",
        )


@dataclass
class ToolParameter:
    """
    Descrição de um parâmetro de uma tool (para geração do JSON Schema).

    Exemplo:
        ToolParameter(
            name="path",
            type="string",
            description="Caminho do arquivo a ler",
            required=True,
        )
    """

    name: str
    type: str                            # "string" | "integer" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    enum: Optional[list[Any]] = None     # Valores aceitos (para type="string")
    default: Optional[Any] = None        # Valor padrão
    items: Optional[dict[str, Any]] = None  # Para type="array"

    def to_schema_property(self) -> dict[str, Any]:
        """Converte para propriedade JSON Schema."""
        prop: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            prop["enum"] = self.enum
        if self.default is not None:
            prop["default"] = self.default
        if self.items and self.type == "array":
            prop["items"] = self.items
        return prop


# ---------------------------------------------------------------------------
# Interface abstrata
# ---------------------------------------------------------------------------


class BaseTool(ABC):
    """
    Contrato que toda tool do agente deve implementar.

    Cada subclasse define:
      - name        : identificador único (snake_case)
      - description : descrição clara para o modelo LLM
      - category    : agrupamento na TUI
      - parameters  : lista de ToolParameter
      - is_destructive : se True, bloqueado em modo 'plan' e requer confirmação em 'agent'

    Exemplo de implementação:
        class ReadFileTool(BaseTool):
            name = "read_file"
            description = "Lê o conteúdo de um arquivo"
            category = ToolCategory.FILESYSTEM
            is_destructive = False
            parameters = [
                ToolParameter("path", "string", "Caminho do arquivo", required=True),
            ]

            async def execute(self, path: str, **kwargs) -> ToolResult:
                content = Path(path).read_text()
                return ToolResult.success(content)
    """

    # -- Atributos obrigatórios --
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.FILESYSTEM
    is_destructive: bool = False         # Se True: bloqueado em 'plan', confirmação em 'agent'
    parameters: list[ToolParameter] = []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Executa a tool com os argumentos fornecidos pelo modelo.

        Args:
            **kwargs: Argumentos conforme definido em self.parameters.

        Returns:
            ToolResult com o resultado da execução.
        """
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """
        Serializa a tool para o formato OpenAI function calling.

        Retorna um dict compatível com o parâmetro 'tools' da API:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_schema_property()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def get_display_info(self) -> dict[str, Any]:
        """
        Retorna informações de exibição da tool para a TUI.

        Returns:
            Dict com name, description, category, is_destructive, parameters_count
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "is_destructive": self.is_destructive,
            "parameters_count": len(self.parameters),
            "required_params": [p.name for p in self.parameters if p.required],
        }

    def __repr__(self) -> str:
        destructive = " ⚠️" if self.is_destructive else ""
        return f"Tool({self.name!r}{destructive})"
