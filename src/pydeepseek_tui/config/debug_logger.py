from datetime import datetime, timezone

from pydeepseek_tui.config.settings import CONFIG_DIR, settings

DEBUG_DIR = CONFIG_DIR / "sessions"


class DebugLogger:
    """Regista atividade de debug quando APP_DEBUG=true."""

    _instance: "DebugLogger | None" = None
    _initialized: bool = False

    def __init__(self, session_id: str | None = None) -> None:
        if session_id:
            self.session_dir = DEBUG_DIR / session_id
        else:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.session_dir = DEBUG_DIR / f"debug_{ts}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self.session_dir / "debug.log"
        self._line_count = 0

    def _write_log(self, level: str, text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        line = f"[{now}] [{level}] {text}\n"
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line)
        self._line_count += 1

    def log_user_input(self, text: str) -> None:
        self._write_log("USER", text)

    def log_output(self, text: str) -> None:
        self._write_log("OUTPUT", text)

    def log_error(self, text: str) -> None:
        self._write_log("ERROR", text)

    def log_system(self, text: str) -> None:
        self._write_log("SYSTEM", text)

    def log_tool_call(self, tool_name: str, args: str, result: str) -> None:
        self._write_log(
            "TOOL",
            f"name={tool_name} args={args[:500]} result={result[:1000]}",
        )

    @classmethod
    def init(cls, session_id: str) -> "DebugLogger | None":
        if not settings.app_debug:
            return None
        cls._instance = cls(session_id=session_id)
        cls._initialized = True
        return cls._instance

    @classmethod
    def get_instance(cls) -> "DebugLogger | None":
        if not settings.app_debug:
            return None
        if cls._instance is None and not cls._initialized:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._initialized = False
