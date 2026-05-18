from pydeepseek_tui.i18n.translator import Translator, LOCALES_DIR


class TestTranslator:
    def test_load_pt_br(self):
        t = Translator("pt_BR")
        assert t.t("app.title") == "PyDeepSeek TUI"

    def test_load_en_us(self):
        t = Translator("en_US")
        assert t.t("app.greeting") == "Welcome to PyDeepSeek TUI"

    def test_fallback_to_en(self):
        t = Translator("pt_BR")
        result = t.t("mode.agent")
        assert result in ("Agente", "Agent")

    def test_missing_key_returns_key(self):
        t = Translator("pt_BR")
        result = t.t("chave.inexistente.xyz")
        assert result == "chave.inexistente.xyz"

    def test_variable_substitution(self):
        t = Translator("pt_BR")
        result = t.t("cli.key_missing", provider="DeepSeek")
        assert "DeepSeek" in result

    def test_missing_locale_falls_back(self):
        t = Translator("fr_FR")
        assert t.locale == "fr_FR"


def test_locales_dir_exists():
    assert LOCALES_DIR.exists()
    assert (LOCALES_DIR / "pt_BR.json").exists()
    assert (LOCALES_DIR / "en_US.json").exists()
