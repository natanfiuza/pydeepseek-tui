import json
import shutil
import uuid
from datetime import datetime, timezone
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
    session_id: str | None = None,
) -> str:
    """Guarda uma sessao e devolve o ID. Usa pastas UUID."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sid = session_id or str(uuid.uuid4())
    session = Session(
        id=sid,
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=provider,
        model=model,
        mode=mode,
        conversation_history=conversation_history,
        metadata=metadata or {},
    )
    session_dir = SESSIONS_DIR / sid
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "session.json"
    path.write_text(
        json.dumps(session.__dict__, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return sid


def load_session(session_id: str) -> Session | None:
    """Carrega uma sessao pelo ID a partir da pasta."""
    path = SESSIONS_DIR / session_id / "session.json"
    if not path.exists():
        # Fallback: old flat file format
        old_path = SESSIONS_DIR / f"{session_id}.json"
        if old_path.exists():
            try:
                data = json.loads(old_path.read_text(encoding="utf-8"))
                return Session(**data)
            except (json.JSONDecodeError, TypeError):
                return None
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def list_sessions() -> List[Session]:
    """Lista todas as sessoes salvas (pastas e ficheiros legacy)."""
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for child in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if child.is_dir():
            session_file = child / "session.json"
            if session_file.exists():
                try:
                    data = json.loads(session_file.read_text(encoding="utf-8"))
                    sessions.append(Session(**data))
                except (json.JSONDecodeError, TypeError):
                    pass
        elif child.suffix == ".json" and child.name != "manifest.json":
            try:
                data = json.loads(child.read_text(encoding="utf-8"))
                sessions.append(Session(**data))
            except (json.JSONDecodeError, TypeError):
                pass
    return sessions


def delete_session(session_id: str) -> bool:
    """Apaga uma sessao pelo ID (pasta ou ficheiro legacy)."""
    session_dir = SESSIONS_DIR / session_id
    if session_dir.is_dir():
        shutil.rmtree(str(session_dir))
        return True
    old_path = SESSIONS_DIR / f"{session_id}.json"
    if old_path.exists():
        old_path.unlink()
        return True
    return False
