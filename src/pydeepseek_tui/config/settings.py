import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import dotenv_values

CONFIG_DIR = Path.home() / ".deepseek-tui"
ENV_FILE = CONFIG_DIR / ".env"


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in ("true", "1", "yes", "on")


@dataclass
class Settings:
    """Armazena as configuracoes globais da aplicacao."""
    ia_provider: str = "deepseek"
    language: str = "pt_BR"
    app_debug: bool = False
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"


def load_settings() -> Settings:
    """Lê as configurações do .env e variáveis de ambiente."""
    env_vars = {}
    if ENV_FILE.exists():
        env_vars = dotenv_values(ENV_FILE)

    debug_raw = env_vars.get("APP_DEBUG") or os.environ.get("APP_DEBUG")
    app_debug = _to_bool(debug_raw)

    provider = env_vars.get("IA_PROVIDER") or os.environ.get("IA_PROVIDER", "deepseek")
    language = env_vars.get("LANGUAGE") or os.environ.get("LANGUAGE", "pt_BR")
    model = env_vars.get("DEEPSEEK_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
    base_url = env_vars.get("DEEPSEEK_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    ds_api_key = os.environ.get("DEEPSEEK_API_KEY")
    oai_api_key = os.environ.get("OPENAI_API_KEY")
    ant_api_key = os.environ.get("ANTHROPIC_API_KEY")

    return Settings(
        ia_provider=provider,
        language=language,
        app_debug=app_debug,
        deepseek_api_key=ds_api_key,
        deepseek_model=model,
        deepseek_base_url=base_url,
        openai_api_key=oai_api_key,
        openai_model=env_vars.get("OPENAI_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o"),
        anthropic_api_key=ant_api_key,
        anthropic_model=env_vars.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    )


settings = load_settings()
