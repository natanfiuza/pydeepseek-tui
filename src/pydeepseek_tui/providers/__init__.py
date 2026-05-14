"""
providers/__init__.py
=====================

ProviderFactory — instancia o provider correto a partir das configurações.

Uso:
    from pydeepseek_tui.providers import ProviderFactory

    # Cria o provider ativo (lê IA_PROVIDER do .env)
    provider = ProviderFactory.from_settings()

    # Cria um provider específico
    provider = ProviderFactory.create(Provider.DEEPSEEK)

    # Lista providers disponíveis (com API key configurada)
    available = ProviderFactory.available_providers()
"""

from __future__ import annotations

import logging
from typing import Optional

from pydeepseek_tui.config.settings import (
    AgentMode,
    Provider,
    Settings,
    get_settings,
)
from pydeepseek_tui.providers.anthropic import AnthropicProvider
from pydeepseek_tui.providers.base import BaseProvider, ModelInfo
from pydeepseek_tui.providers.deepseek import DeepSeekProvider
from pydeepseek_tui.providers.ollama import OllamaProvider
from pydeepseek_tui.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)

__all__ = [
    # Factory
    "ProviderFactory",
    # Providers
    "BaseProvider",
    "DeepSeekProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "AnthropicProvider",
    # Tipos base (re-exportados para conveniência)
    "Provider",
]


class ProviderFactory:
    """
    Fábrica de providers de IA.

    Centraliza a lógica de instanciação, validação e descoberta
    de providers disponíveis com base nas configurações do usuário.

    Extensibilidade:
        Para adicionar um novo provider (ex: Gemini):
          1. Crie src/providers/gemini.py herdando BaseProvider
          2. Adicione Provider.GEMINI ao enum em config/settings.py
          3. Adicione a entrada em _REGISTRY abaixo
          4. Adicione as variáveis no .env (GEMINI_MODEL, GEMINI_API_KEY_ENCRYPTED)
    """

    # ------------------------------------------------------------------
    # Registro central de providers
    # Adicione novos providers aqui sem tocar no restante do código.
    # ------------------------------------------------------------------
    _REGISTRY: dict[Provider, type[BaseProvider]] = {
        Provider.DEEPSEEK: DeepSeekProvider,
        Provider.OPENAI: OpenAIProvider,
        Provider.OLLAMA: OllamaProvider,
        Provider.ANTHROPIC: AnthropicProvider,
    }

    # Metadados dos providers para exibição na TUI
    _METADATA: dict[Provider, dict[str, str]] = {
        Provider.DEEPSEEK: {
            "name": "DeepSeek",
            "icon": "🤖",
            "url": "https://platform.deepseek.com/api_keys",
            "description": "Provider padrão — DeepSeek V4 Pro com 1M tokens de contexto",
        },
        Provider.OPENAI: {
            "name": "OpenAI",
            "icon": "✨",
            "url": "https://platform.openai.com/api-keys",
            "description": "GPT-4o, o3, o4-mini — modelos líderes da OpenAI",
        },
        Provider.OLLAMA: {
            "name": "Ollama (local)",
            "icon": "🏠",
            "url": "https://ollama.com",
            "description": "Modelos locais gratuitos — sem envio de dados à nuvem",
        },
        Provider.ANTHROPIC: {
            "name": "Anthropic",
            "icon": "🧠",
            "url": "https://console.anthropic.com/settings/keys",
            "description": "Claude 3.5/3.7 — especialista em raciocínio e análise",
        },
    }

    # ------------------------------------------------------------------
    # Criação de providers
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        provider: Provider,
        settings: Optional[Settings] = None,
    ) -> BaseProvider:
        """
        Instancia um provider específico com as configurações do usuário.

        Args:
            provider: Provider desejado (ex: Provider.DEEPSEEK)
            settings: Configurações. Se None, usa get_settings().

        Returns:
            Instância do provider pronta para uso.

        Raises:
            ValueError: Se o provider não estiver registrado ou
                        a API key não estiver configurada.
            KeyError: Se o provider não existir no registro.
        """
        cfg = settings or get_settings()

        provider_class = cls._REGISTRY.get(provider)
        if provider_class is None:
            available = ", ".join(p.value for p in cls._REGISTRY)
            raise KeyError(
                f"Provider '{provider.value}' não registrado. "
                f"Disponíveis: {available}"
            )

        # Monta os kwargs conforme o provider
        kwargs = cls._build_kwargs(provider, cfg)

        logger.debug(
            "Instanciando provider '%s' com modelo '%s'",
            provider.value,
            kwargs.get("model", "desconhecido"),
        )

        return provider_class(**kwargs)

    @classmethod
    def from_settings(cls, settings: Optional[Settings] = None) -> BaseProvider:
        """
        Instancia o provider ativo definido em IA_PROVIDER no .env

        Args:
            settings: Configurações. Se None, usa get_settings().

        Returns:
            Provider ativo pronto para uso.
        """
        cfg = settings or get_settings()
        return cls.create(cfg.provider, cfg)

    @classmethod
    def _build_kwargs(cls, provider: Provider, cfg: Settings) -> dict:
        """
        Constrói os kwargs de inicialização para cada provider.

        Centralizar aqui garante que novos providers só precisem
        adicionar sua entrada neste método.
        """
        base_kwargs = {"timeout": cfg.request_timeout, "max_tokens": cfg.max_tokens}

        if provider == Provider.DEEPSEEK:
            return {
                **base_kwargs,
                "api_key": cfg.get_api_key(Provider.DEEPSEEK),
                "model": cfg.deepseek_model,
                "base_url": cfg.deepseek_base_url,
            }

        if provider == Provider.OPENAI:
            return {
                **base_kwargs,
                "api_key": cfg.get_api_key(Provider.OPENAI),
                "model": cfg.openai_model,
                "base_url": cfg.openai_base_url,
            }

        if provider == Provider.OLLAMA:
            return {
                **base_kwargs,
                "api_key": "ollama",
                "model": cfg.ollama_model,
                "base_url": cfg.ollama_base_url,
                "timeout": max(cfg.request_timeout, 300),  # Mínimo 5min para modelos locais
            }

        if provider == Provider.ANTHROPIC:
            return {
                **base_kwargs,
                "api_key": cfg.get_api_key(Provider.ANTHROPIC),
                "model": cfg.anthropic_model,
            }

        # Fallback genérico (para providers registrados via extensão)
        return {
            **base_kwargs,
            "api_key": cfg.get_api_key(provider),
            "model": "unknown",
        }

    # ------------------------------------------------------------------
    # Descoberta e listagem
    # ------------------------------------------------------------------

    @classmethod
    def available_providers(
        cls, settings: Optional[Settings] = None
    ) -> list[Provider]:
        """
        Retorna a lista de providers que possuem API key configurada
        (ou que não precisam de key, como Ollama).

        Args:
            settings: Configurações. Se None, usa get_settings().

        Returns:
            Lista de providers prontos para uso.
        """
        cfg = settings or get_settings()
        available: list[Provider] = []

        for provider in cls._REGISTRY:
            if cfg.is_configured(provider):
                available.append(provider)

        return available

    @classmethod
    def all_providers(cls) -> list[Provider]:
        """Retorna todos os providers registrados (configurados ou não)."""
        return list(cls._REGISTRY.keys())

    @classmethod
    def get_metadata(cls, provider: Provider) -> dict[str, str]:
        """
        Retorna metadados de exibição de um provider (nome, ícone, URL, descrição).

        Args:
            provider: Provider desejado.

        Returns:
            Dict com keys: name, icon, url, description
        """
        return cls._METADATA.get(
            provider,
            {
                "name": provider.value.capitalize(),
                "icon": "🔌",
                "url": "",
                "description": f"Provider {provider.value}",
            },
        )

    @classmethod
    def provider_summary(cls, settings: Optional[Settings] = None) -> list[dict]:
        """
        Retorna um resumo de todos os providers para exibição na TUI.

        Cada item contém:
          - provider: Provider enum
          - name, icon, description, url: metadados
          - configured: bool — tem API key?
          - active: bool — é o provider atual?
          - model: str — modelo configurado

        Args:
            settings: Configurações. Se None, usa get_settings().

        Returns:
            Lista de dicts com informações de cada provider.
        """
        cfg = settings or get_settings()
        summary: list[dict] = []

        model_map = {
            Provider.DEEPSEEK: cfg.deepseek_model,
            Provider.OPENAI: cfg.openai_model,
            Provider.OLLAMA: cfg.ollama_model,
            Provider.ANTHROPIC: cfg.anthropic_model,
        }

        for provider in cls._REGISTRY:
            meta = cls.get_metadata(provider)
            summary.append({
                "provider": provider,
                "name": meta["name"],
                "icon": meta["icon"],
                "description": meta["description"],
                "url": meta["url"],
                "configured": cfg.is_configured(provider),
                "active": provider == cfg.provider,
                "model": model_map.get(provider, "—"),
            })

        # Provider ativo sempre primeiro
        summary.sort(key=lambda x: (not x["active"], not x["configured"], x["name"]))
        return summary

    @classmethod
    async def health_check_all(
        cls, settings: Optional[Settings] = None
    ) -> dict[Provider, bool]:
        """
        Executa health_check() em todos os providers configurados.

        Útil para a tela de diagnóstico na TUI.

        Returns:
            Dict mapeando Provider → bool (True = saudável)
        """
        import asyncio

        cfg = settings or get_settings()
        results: dict[Provider, bool] = {}

        async def _check(provider: Provider) -> tuple[Provider, bool]:
            try:
                instance = cls.create(provider, cfg)
                healthy = await instance.health_check()
                return provider, healthy
            except Exception as exc:
                logger.debug("Health check falhou para '%s': %s", provider.value, exc)
                return provider, False

        configured = cls.available_providers(cfg)
        checks = await asyncio.gather(*[_check(p) for p in configured])

        for provider, healthy in checks:
            results[provider] = healthy

        return results

    @classmethod
    async def list_models_for(
        cls,
        provider: Provider,
        settings: Optional[Settings] = None,
    ) -> list[ModelInfo]:
        """
        Lista modelos disponíveis para um provider específico.

        Args:
            provider: Provider desejado.
            settings: Configurações. Se None, usa get_settings().

        Returns:
            Lista de ModelInfo ordenada por relevância.
        """
        try:
            instance = cls.create(provider, settings)
            return await instance.list_models()
        except Exception as exc:
            logger.warning(
                "Não foi possível listar modelos para '%s': %s",
                provider.value,
                exc,
            )
            return []
