import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any
from pydeepseek_tui.config.settings import CONFIG_DIR

SESSIONS_DIR = CONFIG_DIR / "sessions"


@dataclass
class Session:
    id: str
    timestamp: str
    provider: str
    model: str
    mode: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def preview(self) -> str:
        for msg in self.conversation_history:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                return content[:100] + "..." if len(content) > 100 else content
        return "(sem mensagens)"


def save_session(
    conversation_history: List[Dict[str, Any]],
    provider: str = "deepseek",
    model: str = "",
    mode: str = "agent",
    metadata: Dict[str, str] | None = None,
) -> str:
    """Guarda uma sessao e devolve o ID."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_id = uuid.uuid4().hex[:12]
    session = Session(
        id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=provider,
        model=model,
        mode=mode,
        conversation_history=conversation_history,
        metadata=metadata or {},
    )
    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(
        json.dumps(session.__dict__, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return session_id


def load_session(session_id: str) -> Session | None:
    """Carrega uma sessao pelo ID."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def list_sessions() -> List[Session]:
    """Lista todas as sessoes salvas."""
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(Session(**data))
        except (json.JSONDecodeError, TypeError):
            pass
    return sessions


def delete_session(session_id: str) -> bool:
    """Apaga uma sessao pelo ID."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True
