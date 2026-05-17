import pytest
from pydeepseek_tui.tools.write_file import WriteFileTool


@pytest.fixture
def write_tool():
    return WriteFileTool()


def _allow_all(monkeypatch):
    monkeypatch.setattr(
        "pydeepseek_tui.tools.write_file.is_path_allowed",
        lambda fp, ad=None: True,
    )


@pytest.mark.asyncio
async def test_write_success(write_tool, tmp_path, monkeypatch):
    _allow_all(monkeypatch)
    dest = tmp_path / "novo.txt"
    result = await write_tool.execute(file_path=str(dest), content="conteudo")
    assert "Sucesso" in result
    assert dest.read_text(encoding="utf-8") == "conteudo"


@pytest.mark.asyncio
async def test_write_outside_allowed_dir(write_tool):
    result = await write_tool.execute(file_path="/fora/do/alcance.txt", content="x")
    assert "Erro de seguranca" in result


@pytest.mark.asyncio
async def test_write_file_exists_no_overwrite(write_tool, tmp_path, monkeypatch):
    _allow_all(monkeypatch)
    dest = tmp_path / "existente.txt"
    dest.write_text("original")
    result = await write_tool.execute(file_path=str(dest), content="novo")
    assert "ja existe" in result
    assert dest.read_text(encoding="utf-8") == "original"


@pytest.mark.asyncio
async def test_write_file_exists_with_overwrite(write_tool, tmp_path, monkeypatch):
    _allow_all(monkeypatch)
    dest = tmp_path / "existente.txt"
    dest.write_text("original")
    result = await write_tool.execute(
        file_path=str(dest), content="novo", overwrite=True
    )
    assert "Sucesso" in result
    assert dest.read_text(encoding="utf-8") == "novo"


@pytest.mark.asyncio
async def test_write_missing_path(write_tool, monkeypatch):
    _allow_all(monkeypatch)
    result = await write_tool.execute()
    assert "Erro" in result


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(write_tool, tmp_path, monkeypatch):
    _allow_all(monkeypatch)
    dest = tmp_path / "sub" / "nested" / "file.txt"
    result = await write_tool.execute(file_path=str(dest), content="profundo")
    assert "Sucesso" in result
    assert dest.read_text(encoding="utf-8") == "profundo"
