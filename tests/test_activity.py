import json
import shutil
from pydeepseek_tui.agent.activity import SessionActivityLogger, SESSIONS_DIR


class TestSessionActivityLogger:
    def setup_method(self):
        SessionActivityLogger.reset()

    def test_create_logger_creates_folder_and_manifest(self):
        logger = SessionActivityLogger()
        assert len(logger.session_id) == 36
        assert logger.session_dir.is_dir()
        assert (logger.session_dir / "interactions.json").exists()

    def test_log_interaction_persists(self):
        logger = SessionActivityLogger()
        logger.log_interaction(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=10,
            cost_usd=0.001,
            provider="deepseek",
            model="deepseek-v4-pro",
            prompt_preview="Hello",
            response_preview="Hi there!",
        )
        stats = logger.get_stats()
        assert stats["total_tokens"] == 150
        assert stats["total_cost"] == 0.001
        assert stats["interaction_count"] == 1

        interactions = json.loads(
            (logger.session_dir / "interactions.json").read_text(encoding="utf-8")
        )
        assert len(interactions) == 1
        assert interactions[0]["prompt_tokens"] == 100
        assert interactions[0]["completion_tokens"] == 50

    def test_get_stats_empty(self):
        logger = SessionActivityLogger()
        stats = logger.get_stats()
        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["interaction_count"] == 0
        assert stats["elapsed_seconds"] >= 0

    def test_singleton(self):
        SessionActivityLogger.reset()
        logger1 = SessionActivityLogger.get_instance()
        logger2 = SessionActivityLogger.get_instance()
        assert logger1 is logger2

    def test_multiple_interactions_accumulate(self):
        logger = SessionActivityLogger()
        logger.log_interaction(prompt_tokens=10, completion_tokens=5, cost_usd=0.0001)
        logger.log_interaction(prompt_tokens=20, completion_tokens=10, cost_usd=0.0002)
        stats = logger.get_stats()
        assert stats["total_tokens"] == 45
        assert stats["total_cost"] == 0.0003
        assert stats["interaction_count"] == 2

    def test_update_metadata(self):
        logger = SessionActivityLogger()
        logger.update_metadata(provider="deepseek", model="v4-pro", mode="agent")
        manifest = json.loads(
            (logger.session_dir.parent / "manifest.json").read_text(encoding="utf-8")
        )
        entry = next(s for s in manifest if s["session_id"] == logger.session_id)
        assert entry.get("provider") == "deepseek"
        assert entry.get("model") == "v4-pro"
        assert entry.get("mode") == "agent"

    def test_set_saved(self):
        logger = SessionActivityLogger()
        logger.set_saved()
        manifest = json.loads(
            (logger.session_dir.parent / "manifest.json").read_text(encoding="utf-8")
        )
        entry = next(s for s in manifest if s["session_id"] == logger.session_id)
        assert entry.get("is_saved") is True

    def test_preview_truncation(self):
        logger = SessionActivityLogger()
        long_prompt = "x" * 300
        long_response = "y" * 300
        logger.log_interaction(
            prompt_tokens=1,
            completion_tokens=1,
            prompt_preview=long_prompt,
            response_preview=long_response,
        )
        interactions = json.loads(
            (logger.session_dir / "interactions.json").read_text(encoding="utf-8")
        )
        assert len(interactions[0]["prompt_preview"]) <= 200
        assert len(interactions[0]["response_preview"]) <= 200

    def test_manifest_accumulates_sessions(self):
        logger1 = SessionActivityLogger()
        sid1 = logger1.session_id
        logger1.log_interaction(prompt_tokens=10, completion_tokens=5)

        # Force a second instance with a new UUID (simulate new session)
        SessionActivityLogger.reset()
        logger2 = SessionActivityLogger()
        sid2 = logger2.session_id
        logger2.log_interaction(prompt_tokens=20, completion_tokens=10)

        manifest = json.loads(
            (SESSIONS_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        assert isinstance(manifest, list)
        assert len(manifest) >= 2
        sids = [s["session_id"] for s in manifest]
        assert sid1 in sids
        assert sid2 in sids

        # Cleanup both
        shutil.rmtree(str(logger1.session_dir), ignore_errors=True)
        shutil.rmtree(str(logger2.session_dir), ignore_errors=True)
        SessionActivityLogger.reset()

    def test_current_session_id_global(self):
        from pydeepseek_tui.agent import activity

        SessionActivityLogger.reset()
        logger = SessionActivityLogger()
        assert activity.current_session_id == logger.session_id

    def teardown_method(self):
        if SessionActivityLogger._instance is not None:
            shutil.rmtree(
                str(SessionActivityLogger._instance.session_dir),
                ignore_errors=True,
            )
        SessionActivityLogger.reset()
