import os
from dotenv import dotenv_values
import click
from pydeepseek_tui.app import PyDeepSeekApp
from pydeepseek_tui.config.crypto import encrypt_key, decrypt_key
from pydeepseek_tui.config.settings import ENV_FILE, CONFIG_DIR, settings

PROVIDER_API_KEY_VARS = {
    "deepseek": ("DEEPSEEK_API_KEY_ENCRYPTED", "DEEPSEEK_API_KEY"),
    "openai": ("OPENAI_API_KEY_ENCRYPTED", "OPENAI_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY_ENCRYPTED", "ANTHROPIC_API_KEY"),
}

PROVIDER_KEY_URLS = {
    "deepseek": "https://platform.deepseek.com/api_keys",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
}

MODEL_DEFAULTS = {
    "deepseek": "deepseek-v4-pro",
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
}


def _load_decrypted_api_key(provider: str) -> str | None:
    if not ENV_FILE.exists():
        return None
    encrypted_var, _ = PROVIDER_API_KEY_VARS.get(provider, (None, None))
    if not encrypted_var:
        return None
    env_vars = dotenv_values(ENV_FILE)
    encrypted = env_vars.get(encrypted_var)
    if not encrypted:
        return None
    try:
        return decrypt_key(encrypted)
    except Exception:
        return None


def _save_encrypted_api_key(api_key: str, provider: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    encrypted = encrypt_key(api_key)
    encrypted_var, _ = PROVIDER_API_KEY_VARS.get(provider, (None, None))

    existing = {}
    if ENV_FILE.exists():
        existing = dotenv_values(ENV_FILE)

    prefix = provider.upper()
    defaults = {
        "IA_PROVIDER": provider,
        "LANGUAGE": existing.get("LANGUAGE", "pt_BR"),
        f"{prefix}_MODEL": existing.get(
            f"{prefix}_MODEL", MODEL_DEFAULTS.get(provider, "")
        ),
    }
    if provider == "deepseek":
        defaults["DEEPSEEK_BASE_URL"] = existing.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"{encrypted_var}={encrypted}\n")
        for key, value in defaults.items():
            f.write(f"{key}={value}\n")
        for key, value in existing.items():
            if key != encrypted_var and key not in defaults and value:
                f.write(f"{key}={value}\n")


def ensure_api_key(provider: str | None = None) -> str:
    provider = provider or settings.ia_provider
    api_key = _load_decrypted_api_key(provider)

    if not api_key:
        provider_name = provider.capitalize()
        click.secho(
            f"\nChave da API do {provider_name} nao encontrada!",
            fg="yellow",
            bold=True,
        )
        url = PROVIDER_KEY_URLS.get(provider, "")
        if url:
            click.echo(f"Gere a sua em: {url}\n")
        api_key = click.prompt("Cola a tua chave da API aqui", hide_input=True)
        _save_encrypted_api_key(api_key, provider)
        click.secho("Chave encriptada e salva com sucesso!\n", fg="green", bold=True)

    return api_key


@click.group()
def main() -> None:
    """CLI para o PyDeepSeek TUI."""
    pass


@main.command()
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["deepseek", "openai", "anthropic"]),
    help="Provedor de IA a utilizar.",
)
@click.option("--model", "-m", help="Modelo a utilizar.")
@click.option(
    "--mode",
    type=click.Choice(["plan", "agent", "yolo"]),
    help="Modo de operacao.",
)
@click.option(
    "--lang",
    type=click.Choice(["pt_BR", "en_US"]),
    help="Idioma da interface.",
)
def start(
    provider: str | None, model: str | None, mode: str | None, lang: str | None
) -> None:
    """Inicia a interface grafica no terminal (TUI)."""
    provider_name = provider or settings.ia_provider
    api_key = ensure_api_key(provider_name)

    _, env_var = PROVIDER_API_KEY_VARS.get(provider_name, (None, None))
    if env_var:
        os.environ[env_var] = api_key
    if provider:
        os.environ["IA_PROVIDER"] = provider
    if model:
        prefix = provider_name.upper()
        os.environ[f"{prefix}_MODEL"] = model
    if mode:
        os.environ["PYDEEPSEEK_MODE"] = mode
    if lang:
        os.environ["LANGUAGE"] = lang

    try:
        app = PyDeepSeekApp()
        app.run()
    except ValueError as e:
        click.secho(f"Erro: {e}", fg="red", bold=True)
        click.echo(
            "Verifica a configuracao IA_PROVIDER no ficheiro .env "
            "ou define a chave de API adequada."
        )
        raise SystemExit(1)


@main.command()
def config() -> None:
    """Assistente interativo de configuracao."""
    click.secho("\n=== Configuracao do PyDeepSeek TUI ===\n", bold=True)

    click.echo("Provedores disponiveis: deepseek, openai, anthropic")
    provider = click.prompt(
        "Provedor padrao",
        default=settings.ia_provider,
        type=click.Choice(["deepseek", "openai", "anthropic"]),
    )

    existing_key = _load_decrypted_api_key(provider)
    if existing_key:
        click.echo(f"Chave da API para {provider}: ja configurada.")
        if click.confirm("Desejas alterar a chave?", default=False):
            new_key = click.prompt(
                f"Nova chave da API para {provider}",
                hide_input=True,
            )
            _save_encrypted_api_key(new_key, provider)
            click.secho("Chave atualizada!\n", fg="green")
    else:
        url = PROVIDER_KEY_URLS.get(provider, "")
        if url:
            click.echo(f"Gere a chave em: {url}")
        new_key = click.prompt(
            f"Chave da API para {provider}",
            hide_input=True,
        )
        _save_encrypted_api_key(new_key, provider)
        click.secho("Chave salva!\n", fg="green")

    default_model = MODEL_DEFAULTS.get(provider, "")
    model = click.prompt(
        "Modelo",
        default=default_model,
    )

    lang = click.prompt(
        "Idioma",
        default=settings.language,
        type=click.Choice(["pt_BR", "en_US"]),
    )

    # Update .env with non-key settings
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if ENV_FILE.exists():
        existing = dotenv_values(ENV_FILE)

    prefix = provider.upper()
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"IA_PROVIDER={provider}\n")
        f.write(f"LANGUAGE={lang}\n")
        f.write(f"{prefix}_MODEL={model}\n")
        for key, value in existing.items():
            if key.startswith("_API_KEY_ENCRYPTED") or key.endswith(
                "_API_KEY_ENCRYPTED"
            ):
                f.write(f"{key}={value}\n")

    click.secho("\nConfiguracao guardada com sucesso!\n", fg="green", bold=True)


@main.command()
def sessions() -> None:
    """Lista sessoes salvas."""
    import json

    sessions_dir = CONFIG_DIR / "sessions"
    click.secho("\n=== Sessoes Salvas ===\n", bold=True)

    if not sessions_dir.exists():
        click.echo("Nenhuma sessao encontrada.")
        return

    found = False
    manifest_path = sessions_dir / "manifest.json"

    # Read root manifest (array format)
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else [data]
            for entry in reversed(entries):
                sid = entry.get("session_id", "?")[:8]
                start = entry.get("session_start", "?")[:19]
                last = entry.get("last_interaction", "?")[:19]
                provider = entry.get("provider", "?")
                is_saved = entry.get("is_saved", False)
                icon = " [salva]" if is_saved else ""
                click.echo(
                    f"  {sid}  inicio={start}  ultima={last}  ({provider}){icon}"
                )
                found = True
        except Exception:
            pass

    # Fallback: scan folder structure for sessions without manifest entries
    for child in sorted(sessions_dir.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        session_path = child / "session.json"
        if not session_path.exists():
            continue
        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
            ts = data.get("timestamp", "?")[:19]
            prv = data.get("provider", "?")
            click.echo(f"  {child.name[:8]}  {ts}  ({prv})")
            found = True
        except Exception:
            click.echo(f"  {child.name[:8]}  (erro ao ler)")

    if not found:
        click.echo("Nenhuma sessao encontrada.")
