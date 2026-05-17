import uuid
from pydeepseek_tui.agent.workspace import Workspace


def _uid():
    return f"test_{uuid.uuid4().hex[:8]}"


class TestWorkspace:
    def test_snapshot_and_undo(self, tmp_path):
        ws = Workspace(session_id=_uid())
        f = tmp_path / "test.txt"
        original = "conteudo original"
        f.write_text(original)

        ws.snapshot(str(f))
        assert str(f) in ws.list_snapshots()

        f.write_text("modificado")
        assert f.read_text() == "modificado"

        assert ws.undo(str(f))
        assert f.read_text() == original
        assert str(f) not in ws.list_snapshots()

    def test_undo_nonexistent(self, tmp_path):
        ws = Workspace(session_id=_uid())
        assert not ws.undo(str(tmp_path / "nunca_snapshotado.txt"))

    def test_undo_all(self, tmp_path):
        ws = Workspace(session_id=_uid())
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a original")
        f2.write_text("b original")

        ws.snapshot(str(f1))
        ws.snapshot(str(f2))

        f1.write_text("a modificado")
        f2.write_text("b modificado")

        count = ws.undo_all()
        assert count == 2
        assert f1.read_text() == "a original"
        assert f2.read_text() == "b original"

    def test_snapshot_skip_duplicate(self, tmp_path):
        ws = Workspace(session_id=_uid())
        f = tmp_path / "dup.txt"
        f.write_text("dado")

        ws.snapshot(str(f))
        ws.snapshot(str(f))
        assert len(ws.list_snapshots()) == 1
