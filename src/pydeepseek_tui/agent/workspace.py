import hashlib
import json
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional
from pydeepseek_tui.config.settings import CONFIG_DIR

WORKSPACE_DIR = CONFIG_DIR / "workspace"


@dataclass
class FileSnapshot:
    path: str
    hash: str
    backup_path: str


class Workspace:
    """Gere snapshots de ficheiros antes de edicoes para permitir undo."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self._dir = WORKSPACE_DIR / session_id
        self._dir.mkdir(parents=True, exist_ok=True)
        self._snapshots: Dict[str, FileSnapshot] = {}
        self._load_index()

    def _index_path(self) -> Path:
        return self._dir / "index.json"

    def _load_index(self) -> None:
        if not self._index_path().exists():
            return
        try:
            data = json.loads(self._index_path().read_text(encoding="utf-8"))
            for item in data:
                snap = FileSnapshot(**item)
                self._snapshots[snap.path] = snap
        except (json.JSONDecodeError, TypeError):
            pass

    def _save_index(self) -> None:
        data = [s.__dict__ for s in self._snapshots.values()]
        self._index_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def snapshot(self, file_path: str) -> None:
        """Cria snapshot de um ficheiro antes de ser modificado."""
        path = Path(file_path)
        if not path.exists():
            return

        content = path.read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()[:16]

        # Evita duplicados
        if file_path in self._snapshots:
            if self._snapshots[file_path].hash == file_hash:
                return

        backup_path = self._dir / f"{len(self._snapshots)}.bak"
        shutil.copy2(str(path), str(backup_path))

        self._snapshots[file_path] = FileSnapshot(
            path=str(path),
            hash=file_hash,
            backup_path=str(backup_path),
        )
        self._save_index()

    def undo(self, file_path: str) -> bool:
        """Restaura um ficheiro ao estado do snapshot."""
        if file_path not in self._snapshots:
            return False

        snap = self._snapshots[file_path]
        backup = Path(snap.backup_path)
        if not backup.exists():
            return False

        shutil.copy2(str(backup), file_path)
        del self._snapshots[file_path]
        self._save_index()
        return True

    def undo_all(self) -> int:
        """Restaura todos os ficheiros desta sessao."""
        count = 0
        for path in list(self._snapshots.keys()):
            if self.undo(path):
                count += 1
        return count

    def list_snapshots(self) -> Dict[str, str]:
        """Devolve {path: hash} dos snapshots ativos."""
        return {p: s.hash for p, s in self._snapshots.items()}
