"""
config/settings.py
==================

Leitura, validação e exposição das configurações do pydeepseek-tui.

O arquivo de configuração fica em ~/.deepseek-tui/.env
As API keys são armazenadas criptografadas (Fernet) e descriptografadas
em memória apenas quando necessário.

Uso:
    from pydeepseek_tui.config.settings import get_settings, Settings

    settings = get_settings()
    print(settings.provider)        # "deepseek"
    print(settings.deepseek_model)  # "deepseek-v4-pro"
    api_key = settings.get_api_key() # descriptografa sob demanda
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, set_key

from pydeepseek_tui.config.crypto import (
    decrypt_api_key,
    encrypt_api_key,
    is_encrypted,
    mask_api_key,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CONFIG_DIR: Path = Path.home() / ".deepseek-tui"
ENV_FILE: Path = CONFIG_DIR / ".env"
SESSIONS_DIR: Path = CONFIG_DIR / "sessions"
SNAPSHOTS_DIR: Path = CONFIG_DIR / "snapshots"

SUPPORTED_LANGUAGES: dict[str, str] = {
    "pt_BR": "Português (Brasil)",
    "en_US": "English (US)",
}

DEFAULT_LANGUAGE: str = "pt_BR"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Provider(str, Enum):
    """Providers de IA suportados."""

    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"


class AgentMode(str, Enum):
    """Modos de operação do agente."""

    PLAN = "plan"      # Somente leitura — nunca executa tools destrutivas
    AGENT = "agent"    # Executa com confirmação do usuário
    YOLO = "yolo"      # Executa sem confirmação


# ---------------------------------------------------------------------------
# Dataclass de configurações
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    """
    Configurações carregadas do ~/.deepseek-tui/.env

    Todas as API keys são mantidas criptografadas neste objeto.
    Use get_api_key() para descriptografar sob demanda.
    """

    # Provider ativo
    provider: Provider = Provider.DEEPSEEK

    # DeepSeek
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com"
    _deepseek_api_key_encrypted: str = field(default="", repr=False)

    # OpenAI (futuro)
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"
    _openai_api_key_encrypted: str = field(default="", repr=False)

    # Anthropic (futuro)
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    _anthropic_api_key_encrypted: str = field(default="", repr=False)

    # Ollama (local, sem API key)
    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"

    # Gemini (futuro — exemplo de extensão)
    # gemini_model: str = "gemini-pro-latest"
    # _gemini_api_key_encrypted: str = field(default="", repr=False)

    # Interface
    language: str = DEFAULT_LANGUAGE
    agent_mode: AgentMode = AgentMode.AGENT
    theme: str = "dark"

    # Limites
    max_tokens: int = 8192
    context_window: int = 65536
    request_timeout: int = 120

    def get_api_key(self, provider: Optional[Provider] = None) -> str:
        """
        Descriptografa e retorna a API key do provider especificado
        (ou do provider ativo, se não informado).

        Args:
            provider: Provider desejado. Default: provider ativo.

        Returns:
            API key em texto plano.

        Raises:
            ValueError: Se a key não estiver configurada ou não puder ser descriptografada.
        """
        target = provider or self.provider

        encrypted_map: dict[Provider, str] = {
            Provider.DEEPSEEK: self._deepseek_api_key_encrypted,
            Provider.OPENAI: self._openai_api_key_encrypted,
            Provider.ANTHROPIC: self._anthropic_api_key_encrypted,
        }

        if target == Provider.OLLAMA:
            return ""  # Ollama local não precisa de API key

        encrypted = encrypted_map.get(target, "")

        if not encrypted:
            raise ValueError(
                f"API key para '{target.value}' não configurada. "
                f"Execute 'pydeepseek-tui config' para configurar."
            )

        return decrypt_api_key(encrypted)

    def get_masked_api_key(self, provider: Optional[Provider] = None) -> str:
        """
        Retorna a API key mascarada para exibição segura (ex: sk-abc1****xyz).

        Não lança exceção — retorna '(não configurada)' se ausente.
        """
        try:
            key = self.get_api_key(provider)
            return mask_api_key(key)
        except ValueError:
            return "(não configurada)"

    def is_configured(self, provider: Optional[Provider] = None) -> bool:
        """Verifica se a API key do provider está configurada."""
        target = provider or self.provider
        if target == Provider.OLLAMA:
            return True
        try:
            self.get_api_key(target)
            return True
        except ValueError:
            return False

    def get_language_name(self) -> str:
        """Retorna o nome legível do idioma configurado."""
        return SUPPORTED_LANGUAGES.get(self.language, self.language)

    def __repr__(self) -> str:
        return (
            f"Settings("
            f"provider={self.provider.value!r}, "
            f"model={self._get_active_model()!r}, "
            f"language={self.language!r}, "
            f"mode={self.agent_mode.value!r}, "
            f"api_key={self.get_masked_api_key()!r}"
            f")"
        )

    def _get_active_model(self) -> str:
        model_map = {
            Provider.DEEPSEEK: self.deepseek_model,
            Provider.OPENAI: self.openai_model,
            Provider.ANTHROPIC: self.anthropic_model,
            Provider.OLLAMA: self.ollama_model,
        }
        return model_map.get(self.provider, "unknown")


# ---------------------------------------------------------------------------
# Carregamento do .env
# ---------------------------------------------------------------------------


def _ensure_config_dir() -> None:
    """Cria o diretório ~/.deepseek-tui/ e subdiretórios se não existirem."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Permissões restritas: somente o dono pode ler/escrever
    CONFIG_DIR.chmod(0o700)


def load_settings() -> Settings:
    """
    Carrega as configurações do arquivo ~/.deepseek-tui/.env

    Se o arquivo não existir, retorna as configurações padrão
    (o usuário precisará rodar 'pydeepseek-tui config').

    Returns:
        Instância de Settings com os valores do .env.
    """
    _ensure_config_dir()

    if not ENV_FILE.exists():
        return Settings()

    values = dotenv_values(ENV_FILE)

    def _get(key: str, default: str = "") -> str:
        return str(values.get(key, default)).strip()

    # Provider
    provider_raw = _get("IA_PROVIDER", "deepseek").lower()
    try:
        provider = Provider(provider_raw)
    except ValueError:
        provider = Provider.DEEPSEEK

    # Modo do agente
    mode_raw = _get("AGENT_MODE", "agent").lower()
    try:
        agent_mode = AgentMode(mode_raw)
    except ValueError:
        agent_mode = AgentMode.AGENT

    # Idioma
    language = _get("LANGUAGE", DEFAULT_LANGUAGE)
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    settings = Settings(
        provider=provider,
        # DeepSeek
        deepseek_model=_get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        deepseek_base_url=_get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        # OpenAI
        openai_model=_get("OPENAI_MODEL", "gpt-4o"),
        openai_base_url=_get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        # Anthropic
        anthropic_model=_get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        # Ollama
        ollama_model=_get("OLLAMA_MODEL", "llama3.2"),
        ollama_base_url=_get("OLLAMA_BASE_URL", "http://localhost:11434"),
        # Interface
        language=language,
        agent_mode=agent_mode,
        theme=_get("THEME", "dark"),
        # Limites
        max_tokens=int(_get("MAX_TOKENS", "8192")),
        context_window=int(_get("CONTEXT_WINDOW", "65536")),
        request_timeout=int(_get("REQUEST_TIMEOUT", "120")),
    )

    # API keys criptografadas (acesso privado via _xxx)
    settings._deepseek_api_key_encrypted = _get("DEEPSEEK_API_KEY_ENCRYPTED")
    settings._openai_api_key_encrypted = _get("OPENAI_API_KEY_ENCRYPTED")
    settings._anthropic_api_key_encrypted = _get("ANTHROPIC_API_KEY_ENCRYPTED")

    return settings


def save_api_key(provider: Provider, api_key_plain: str) -> None:
    """
    Criptografa e salva a API key de um provider no ~/.deepseek-tui/.env

    Args:
        provider: Provider de destino
        api_key_plain: API key em texto plano

    Raises:
        ValueError: Se a key for inválida
    """
    _ensure_config_dir()

    encrypted = encrypt_api_key(api_key_plain)

    key_map: dict[Provider, str] = {
        Provider.DEEPSEEK: "DEEPSEEK_API_KEY_ENCRYPTED",
        Provider.OPENAI: "OPENAI_API_KEY_ENCRYPTED",
        Provider.ANTHROPIC: "ANTHROPIC_API_KEY_ENCRYPTED",
    }

    env_key = key_map.get(provider)
    if not env_key:
        raise ValueError(f"Provider '{provider.value}' não requer API key.")

    set_key(str(ENV_FILE), env_key, encrypted)

    # Garante permissão restrita no .env
    ENV_FILE.chmod(0o600)


def save_setting(key: str, value: str) -> None:
    """
    Salva uma configuração genérica no ~/.deepseek-tui/.env

    Args:
        key: Nome da variável (ex: "LANGUAGE", "DEEPSEEK_MODEL")
        value: Valor a salvar
    """
    _ensure_config_dir()
    set_key(str(ENV_FILE), key, value)
    ENV_FILE.chmod(0o600)


def init_env_file() -> None:
    """
    Cria o ~/.deepseek-tui/.env com os valores padrão caso não exista.
    Chamado automaticamente pelo 'pydeepseek-tui config'.
    """
    _ensure_config_dir()

    if ENV_FILE.exists():
        return

    defaults = {
        "IA_PROVIDER": "deepseek",
        "DEEPSEEK_MODEL": "deepseek-v4-pro",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_API_KEY_ENCRYPTED": "",
        "OPENAI_MODEL": "gpt-4o",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_API_KEY_ENCRYPTED": "",
        "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        "ANTHROPIC_API_KEY_ENCRYPTED": "",
        "OLLAMA_MODEL": "llama3.2",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "LANGUAGE": DEFAULT_LANGUAGE,
        "AGENT_MODE": "agent",
        "THEME": "dark",
        "MAX_TOKENS": "8192",
        "CONTEXT_WINDOW": "65536",
        "REQUEST_TIMEOUT": "120",
        # Futuro — basta descomentar e adicionar a key:
        # "GEMINI_MODEL": "gemini-pro-latest",
        # "GEMINI_API_KEY_ENCRYPTED": "",
    }

    lines = [
        "# ============================================================",
        "# pydeepseek-tui — Configuração",
        "# Gerado automaticamente. NÃO versionar este arquivo.",
        "# ============================================================",
        "",
        "# Provider ativo",
        f'IA_PROVIDER={defaults["IA_PROVIDER"]}',
        "",
        "# ── DeepSeek ─────────────────────────────────────────────────",
        f'DEEPSEEK_MODEL={defaults["DEEPSEEK_MODEL"]}',
        f'DEEPSEEK_BASE_URL={defaults["DEEPSEEK_BASE_URL"]}',
        f'DEEPSEEK_API_KEY_ENCRYPTED={defaults["DEEPSEEK_API_KEY_ENCRYPTED"]}',
        "",
        "# ── OpenAI ───────────────────────────────────────────────────",
        f'OPENAI_MODEL={defaults["OPENAI_MODEL"]}',
        f'OPENAI_BASE_URL={defaults["OPENAI_BASE_URL"]}',
        f'OPENAI_API_KEY_ENCRYPTED={defaults["OPENAI_API_KEY_ENCRYPTED"]}',
        "",
        "# ── Anthropic ────────────────────────────────────────────────",
        f'ANTHROPIC_MODEL={defaults["ANTHROPIC_MODEL"]}',
        f'ANTHROPIC_API_KEY_ENCRYPTED={defaults["ANTHROPIC_API_KEY_ENCRYPTED"]}',
        "",
        "# ── Ollama (local, sem API key) ───────────────────────────────",
        f'OLLAMA_MODEL={defaults["OLLAMA_MODEL"]}',
        f'OLLAMA_BASE_URL={defaults["OLLAMA_BASE_URL"]}',
        "",
        "# ── Futuro: adicione novos providers aqui ────────────────────",
        "# GEMINI_MODEL=gemini-pro-latest",
        "# GEMINI_API_KEY_ENCRYPTED=",
        "",
        "# ── Interface ────────────────────────────────────────────────",
        f'LANGUAGE={defaults["LANGUAGE"]}',
        f'AGENT_MODE={defaults["AGENT_MODE"]}',
        f'THEME={defaults["THEME"]}',
        "",
        "# ── Limites ──────────────────────────────────────────────────",
        f'MAX_TOKENS={defaults["MAX_TOKENS"]}',
        f'CONTEXT_WINDOW={defaults["CONTEXT_WINDOW"]}',
        f'REQUEST_TIMEOUT={defaults["REQUEST_TIMEOUT"]}',
    ]

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


# ---------------------------------------------------------------------------
# Singleton — cache da instância carregada
# ---------------------------------------------------------------------------

_settings_cache: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """
    Retorna a instância singleton de Settings.

    Args:
        reload: Se True, recarrega o .env mesmo que já esteja em cache.

    Returns:
        Settings carregado e validado.
    """
    global _settings_cache  # noqa: PLW0603

    if _settings_cache is None or reload:
        _settings_cache = load_settings()

    return _settings_cache
