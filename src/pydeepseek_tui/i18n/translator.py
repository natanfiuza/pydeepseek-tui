import json
from pathlib import Path
from typing import Dict

LOCALES_DIR = Path(__file__).parent / "locales"


class Translator:
    """Carrega e traduz strings com suporte a fallback e substituicao."""

    _instance: "Translator | None" = None

    def __init__(self, locale: str = "pt_BR") -> None:
        self.locale = locale
        self._strings: Dict[str, str] = {}
        self._fallback: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        self._fallback = self._load_file("en_US")
        self._strings = self._load_file(self.locale)

    def _load_file(self, locale: str) -> Dict[str, str]:
        path = LOCALES_DIR / f"{locale}.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def t(self, key: str, **kwargs: str) -> str:
        text = self._strings.get(key) or self._fallback.get(key) or key
        if kwargs:
            for k, v in kwargs.items():
                text = text.replace(f"{{{k}}}", v)
        return text

    @classmethod
    def get_instance(cls, locale: str = "pt_BR") -> "Translator":
        if cls._instance is None or cls._instance.locale != locale:
            cls._instance = cls(locale)
        return cls._instance


def t(key: str, **kwargs: str) -> str:
    """Funcao de conveniencia para traducao usando o singleton."""
    return Translator.get_instance().t(key, **kwargs)
