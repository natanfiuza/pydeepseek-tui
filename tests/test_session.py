from pydeepseek_tui.agent.session import (
    save_session, load_session, list_sessions, delete_session, Session
)


class TestSession:
    def test_save_and_load(self):
        history = [
            {"role": "user", "content": "ola"},
            {"role": "assistant", "content": "oi, como posso ajudar?"},
        ]
        sid = save_session(
            history, provider="deepseek", model="v4", mode="agent"
        )
        assert len(sid) == 12

        loaded = load_session(sid)
        assert loaded is not None
        assert loaded.provider == "deepseek"
        assert len(loaded.conversation_history) == 2

        delete_session(sid)

    def test_load_nonexistent(self):
        assert load_session("nao_existe_123") is None

    def test_list_and_delete(self):
        sid1 = save_session([{"role": "user", "content": "a"}], provider="openai")
        sid2 = save_session([{"role": "user", "content": "b"}], provider="deepseek")

        sessions = list_sessions()
        ids = [s.id for s in sessions]
        assert sid1 in ids or sid2 in ids

        delete_session(sid1)
        delete_session(sid2)

    def test_session_preview(self):
        session = Session(
            id="test",
            timestamp="2026-01-01T00:00:00Z",
            provider="deepseek",
            model="v4",
            mode="agent",
            conversation_history=[
                {"role": "user", "content": "teste de preview"},
            ],
        )
        assert "teste de preview" in session.preview


def test_session_preview_empty():
    session = Session(
        id="test2",
        timestamp="2026-01-01T00:00:00Z",
        provider="deepseek",
        model="v4",
        mode="agent",
    )
    assert "sem mensagens" in session.preview
