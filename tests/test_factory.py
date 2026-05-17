import pytest


class TestProviderFactory:
    def test_get_deepseek_provider(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")

        from pydeepseek_tui.providers.factory import ProviderFactory
        from pydeepseek_tui.providers.deepseek import DeepSeekProvider

        provider = ProviderFactory.get_provider("deepseek")
        assert isinstance(provider, DeepSeekProvider)

    def test_get_invalid_provider_raises(self):
        from pydeepseek_tui.providers.factory import ProviderFactory

        with pytest.raises(ValueError, match="desconhecido"):
            ProviderFactory.get_provider("provedor_inexistente")
