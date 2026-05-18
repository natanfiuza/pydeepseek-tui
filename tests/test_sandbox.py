import os
from pydeepseek_tui.tools.sandbox import is_path_allowed


class TestIsPathAllowed:
    def test_path_inside_cwd(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert is_path_allowed(str(f), allowed_dirs=[str(tmp_path)])

    def test_path_outside_cwd(self, tmp_path):
        outside = (
            "/etc/passwd"
            if os.name != "nt"
            else "C:\\Windows\\System32\\drivers\\etc\\hosts"
        )
        assert not is_path_allowed(outside, allowed_dirs=[str(tmp_path)])

    def test_path_traversal_blocked(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        traversal = str(sub / ".." / ".." / "etc" / "passwd")
        assert not is_path_allowed(traversal, allowed_dirs=[str(tmp_path)])

    def test_default_allowed_dirs_is_cwd(self):
        assert is_path_allowed(".")

    def test_nonexistent_path(self):
        assert not is_path_allowed("/nonexistent/path/12345", allowed_dirs=["/tmp"])

    def test_multiple_allowed_dirs(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        f = dir_b / "ok.txt"
        f.write_text("ok")
        assert is_path_allowed(str(f), allowed_dirs=[str(dir_a), str(dir_b)])
