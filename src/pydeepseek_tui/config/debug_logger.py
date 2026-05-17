import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from pydeepseek_tui.config.settings import CONFIG_DIR, settings

DEBUG_DIR = CONFIG_DIR / "sessions"


class DebugLogger:
    """Regista toda a atividade quando APP_DEBUG=true."""

    _instance: "DebugLogger | None" = None

    def __init__(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_dir = DEBUG_DIR / f"debug_{ts}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self.session_dir / "session.log"
        self._prompts_path = self.session_dir / "prompts.json"
        self._prompts: List[Dict[str, Any]] = []
        self._line_count = 0

    def _write_log(self, level: str, text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        line = f"[{now}] [{level}] {text}\n"
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line)
        self._line_count += 1

    def _flush_prompts(self) -> None:
        with open(self._prompts_path, "w", encoding="utf-8") as f:
            json.dump(self._prompts, f, ensure_ascii=False, indent=2)

    # --- Text log ---

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

    # --- JSON prompts log ---

    def log_prompt(self, messages: List[Dict[str, Any]], tools: Any = None) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
        }
        if tools:
            entry["tools"] = tools
        self._prompts.append(entry)
        self._flush_prompts()

    def log_reasoning(self, content: str) -> None:
        if not self._prompts:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasoning_content": content,
        }
        self._prompts.append(entry)
        self._flush_prompts()

    def log_tool_result(self, tool_name: str, result: str) -> None:
        if not self._prompts:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "tool_result": result,
        }
        self._prompts.append(entry)
        self._flush_prompts()

    @classmethod
    def get_instance(cls) -> "DebugLogger | None":
        if not settings.app_debug:
            return None
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
