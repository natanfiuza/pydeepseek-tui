"""
agent/session.py
================

Session -- Gerenciamento de sessoes persistentes do agente.

Salva e restaura o historico de conversas em JSON,
permitindo que o usuario retome sessoes anteriores.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydeepseek_tui.providers.base import Message, MessageRole

logger = logging.getLogger(__name__)

_SESSION_DIR = Path.home() / ".pydeepseek_tui" / "sessions"
_MAX_SESSIONS = 50


@dataclass_like = None  # Import abaixo


class Session:
    """Representa uma sessao de conversa serializada."""

    def __init__(
        self,
        session_id: str,
        name: str,
        messages: list[Message],
        provider: str = "",
        model: str = "",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        self.session_id = session_id
        self.name = name
        self.messages = messages
        self.provider = provider
        self.model = model
        self.created_at = created_at or _now()
        self.updated_at = updated_at or self.created_at

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [
                {
                    "role": m.role.value,
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                    "thinking": m.thinking,
                }
                for m in self.messages
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        messages = []
        for m in data.get("messages", []):
            try:
                role = MessageRole(m["role"])
            except ValueError:
                role = MessageRole.USER
            messages.append(Message(
                role=role,
                content=m.get("content", ""),
                tool_call_id=m.get("tool_call_id"),
                thinking=m.get("thinking"),
            ))
        return cls(
            session_id=data["session_id"],
            name=data.get("name", data["session_id"]),
            messages=messages,
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class SessionManager:
    """
    Gerencia sessoes persistentes em disco (~/.pydeepseek_tui/sessions/).

    Uso:
        mgr = SessionManager()
        sid = mgr.save(messages, name="Projeto X", provider="deepseek")
        session = mgr.load(sid)
        all_sessions = mgr.list_sessions()
    """

    def __init__(self, session_dir: Optional[Path] = None) -> None:
        self.session_dir = session_dir or _SESSION_DIR
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        messages: list[Message],
        name: Optional[str] = None,
        provider: str = "",
        model: str = "",
        session_id: Optional[str] = None,
    ) -> str:
        """
        Salva o historico em disco.

        Returns:
            ID da sessao criada/atualizada.
        """
        import uuid
        sid = session_id or str(uuid.uuid4())[:8]
        auto_name = name or _auto_name(messages) or f"Sessao {sid}"

        session = Session(
            session_id=sid,
            name=auto_name,
            messages=messages,
            provider=provider,
            model=model,
            updated_at=_now(),
        )

        path = self.session_dir / f"{sid}.json"
        path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        logger.info("Sessao '%s' salva em %s (%d msgs)", sid, path, len(messages))
        self._cleanup_old_sessions()
        return sid

    def load(self, session_id: str) -> Optional[Session]:
        """Carrega uma sessao do disco pelo ID."""
        path = self.session_dir / f"{session_id}.json"
        if not path.exists():
            logger.warning("Sessao '%s' nao encontrada.", session_id)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Session.from_dict(data)
        except Exception as exc:
            logger.error("Erro ao carregar sessao '%s': %s", session_id, exc)
            return None

    def list_sessions(self) -> list[Session]:
        """Lista todas as sessoes salvas, ordenadas pela mais recente."""
        sessions: list[Session] = []
        for path in self.session_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(Session.from_dict(data))
            except Exception:
                continue
        return sorted(sessions, key=lambda s: s.updated_at or "", reverse=True)

    def delete(self, session_id: str) -> bool:
        """Remove uma sessao do disco."""
        path = self.session_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            logger.info("Sessao '%s' removida.", session_id)
            return True
        return False

    def _cleanup_old_sessions(self) -> None:
        """Remove sessoes mais antigas se o limite for ultrapassado."""
        sessions = self.list_sessions()
        if len(sessions) > _MAX_SESSIONS:
            for old in sessions[_MAX_SESSIONS:]:
                self.delete(old.session_id)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _auto_name(messages: list[Message]) -> Optional[str]:
    for m in messages:
        if m.role == MessageRole.USER and m.content:
            return m.content[:60].replace("\n", " ").strip()
    return None
