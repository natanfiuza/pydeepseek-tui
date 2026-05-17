from pydeepseek_tui.providers.base import BaseAIProvider
from pydeepseek_tui.providers.deepseek import DeepSeekProvider
from pydeepseek_tui.providers.openai import OpenAIProvider
from pydeepseek_tui.providers.anthropic import AnthropicProvider
from pydeepseek_tui.config.settings import settings


class ProviderFactory:
    """Fabrica responsavel por instanciar e retornar o provedor de IA."""

    @staticmethod
    def get_provider(provider_name: str | None = None) -> BaseAIProvider:
        name = provider_name or settings.ia_provider

        if name == "deepseek":
            return DeepSeekProvider()
        if name == "openai":
            return OpenAIProvider()
        if name == "anthropic":
            return AnthropicProvider()

        raise ValueError(
            f"Provedor de IA desconhecido ou nao suportado: {name}. "
            "Provedores disponiveis: deepseek, openai, anthropic."
        )
