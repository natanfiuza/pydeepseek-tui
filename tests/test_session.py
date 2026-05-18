from pydeepseek_tui.agent.session import (
    save_session,
    load_session,
    list_sessions,
    delete_session,
    Session,
    SESSIONS_DIR,
)


class TestSession:
    def test_save_and_load(self):
        history = [
            {"role": "user", "content": "ola"},
            {"role": "assistant", "content": "oi, como posso ajudar?"},
        ]
        sid = save_session(history, provider="deepseek", model="v4", mode="agent")
        assert len(sid) == 36  # full UUID

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


class TestSessionFolderStructure:
    def test_save_creates_folder(self):
        sid = save_session(
            [{"role": "user", "content": "a"}],
            provider="deepseek",
            model="v4",
            mode="agent",
        )
        session_dir = SESSIONS_DIR / sid
        assert session_dir.is_dir()
        assert (session_dir / "session.json").exists()
        delete_session(sid)

    def test_save_with_existing_id(self):
        existing_id = "550e8400-e29b-41d4-a716-446655440000"
        sid = save_session(
            [{"role": "user", "content": "b"}],
            provider="deepseek",
            model="v4",
            mode="agent",
            session_id=existing_id,
        )
        assert sid == existing_id
        session_dir = SESSIONS_DIR / sid
        assert session_dir.is_dir()
        delete_session(sid)

    def test_load_legacy_flat_file(self):
        history = [{"role": "user", "content": "legacy"}]
        session = Session(
            id="legacy12345",
            timestamp="2026-01-01T00:00:00Z",
            provider="deepseek",
            model="v4",
            mode="agent",
            conversation_history=history,
        )
        import json

        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        legacy_path = SESSIONS_DIR / "legacy12345.json"
        legacy_path.write_text(
            json.dumps(session.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        loaded = load_session("legacy12345")
        assert loaded is not None
        assert loaded.id == "legacy12345"
        assert loaded.provider == "deepseek"

        legacy_path.unlink()

    def test_list_includes_legacy_files(self):
        import json

        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session = Session(
            id="oldflat1",
            timestamp="2026-01-01T00:00:00Z",
            provider="anthropic",
            model="claude",
            mode="agent",
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        legacy_path = SESSIONS_DIR / "oldflat1.json"
        legacy_path.write_text(
            json.dumps(session.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        sessions = list_sessions()
        ids = [s.id for s in sessions]
        assert "oldflat1" in ids

        legacy_path.unlink()

    def test_list_skips_manifest_json(self):

        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = SESSIONS_DIR / "manifest.json"
        manifest_path.write_text('{"session_id": "test"}', encoding="utf-8")

        sessions = list_sessions()
        ids = [s.id for s in sessions]
        assert "manifest" not in ids

        manifest_path.unlink()


def test_session_preview_empty():
    session = Session(
        id="test2",
        timestamp="2026-01-01T00:00:00Z",
        provider="deepseek",
        model="v4",
        mode="agent",
    )
    assert "sem mensagens" in session.preview
