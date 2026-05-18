import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydeepseek_tui.config.settings import CONFIG_DIR

SESSIONS_DIR = CONFIG_DIR / "sessions"

# Variavel global com o session_id da sessao ativa.
# Definida pelo SessionActivityLogger ao inicializar.
current_session_id: str | None = None


class SessionActivityLogger:
    _instance: "SessionActivityLogger | None" = None

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.session_dir = SESSIONS_DIR / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self._manifest_path = SESSIONS_DIR / "manifest.json"
        self._interactions_path = self.session_dir / "interactions.json"
        self._interactions: List[Dict[str, Any]] = []

        self._total_tokens = 0
        self._total_cost = 0.0
        self._session_start = datetime.now(timezone.utc)

        global current_session_id
        current_session_id = self.session_id

        self._write_manifest()
        self._flush_interactions()

    def _read_manifest(self) -> List[Dict[str, Any]]:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            # Legacy: single object, convert to list
            return [data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_manifest(self) -> None:
        sessions = self._read_manifest()
        entry = {
            "session_id": self.session_id,
            "session_start": self._session_start.isoformat(),
            "last_interaction": datetime.now(timezone.utc).isoformat(),
        }
        # Update existing entry or append new one
        for i, s in enumerate(sessions):
            if s.get("session_id") == self.session_id:
                sessions[i].update(entry)
                break
        else:
            sessions.append(entry)

        self._manifest_path.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _flush_interactions(self) -> None:
        self._interactions_path.write_text(
            json.dumps(self._interactions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def log_interaction(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        cost_usd: float = 0.0,
        provider: str = "",
        model: str = "",
        prompt_preview: str = "",
        response_preview: str = "",
    ) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": cost_usd,
            "provider": provider,
            "model": model,
            "prompt_preview": prompt_preview[:200],
            "response_preview": response_preview[:200],
        }
        self._interactions.append(entry)
        self._flush_interactions()
        self._total_tokens += entry["total_tokens"]
        self._total_cost += cost_usd
        self._write_manifest()

    def update_metadata(
        self,
        provider: str = "",
        model: str = "",
        mode: str = "",
    ) -> None:
        sessions = self._read_manifest()
        for s in sessions:
            if s.get("session_id") == self.session_id:
                if provider:
                    s["provider"] = provider
                if model:
                    s["model"] = model
                if mode:
                    s["mode"] = mode
                break
        else:
            sessions.append(
                {
                    "session_id": self.session_id,
                    "session_start": self._session_start.isoformat(),
                    "last_interaction": datetime.now(timezone.utc).isoformat(),
                    "provider": provider,
                    "model": model,
                    "mode": mode,
                }
            )
        self._manifest_path.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_saved(self) -> None:
        sessions = self._read_manifest()
        for s in sessions:
            if s.get("session_id") == self.session_id:
                s["is_saved"] = True
                break
        self._manifest_path.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_stats(self) -> Dict[str, Any]:
        elapsed = datetime.now(timezone.utc) - self._session_start
        return {
            "session_id": self.session_id,
            "elapsed_seconds": int(elapsed.total_seconds()),
            "total_tokens": self._total_tokens,
            "total_cost": round(self._total_cost, 6),
            "interaction_count": len(self._interactions),
        }

    @classmethod
    def get_instance(cls) -> "SessionActivityLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        global current_session_id
        current_session_id = None
        cls._instance = None
