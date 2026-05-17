import pytest
from pydeepseek_tui.tools.file_reader import FileReaderTool


@pytest.fixture
def file_reader():
    return FileReaderTool()


@pytest.mark.asyncio
async def test_file_reader_success(file_reader, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pydeepseek_tui.tools.file_reader.is_path_allowed",
        lambda fp, ad=None: True,
    )

    test_file = tmp_path / "test_doc.txt"
    test_file.write_text("Testando a ferramenta do Seu Ze!", encoding="utf-8")

    result = await file_reader.execute(file_path=str(test_file))
    assert result == "Testando a ferramenta do Seu Ze!"


@pytest.mark.asyncio
async def test_file_reader_missing_path(file_reader, monkeypatch):
    monkeypatch.setattr(
        "pydeepseek_tui.tools.file_reader.is_path_allowed",
        lambda fp, ad=None: True,
    )

    result = await file_reader.execute()
    assert "Erro" in result


@pytest.mark.asyncio
async def test_file_reader_not_found(file_reader, monkeypatch):
    monkeypatch.setattr(
        "pydeepseek_tui.tools.file_reader.is_path_allowed",
        lambda fp, ad=None: True,
    )

    result = await file_reader.execute(file_path="caminho_totalmente_inexistente.txt")
    assert "nao foi encontrado" in result


@pytest.mark.asyncio
async def test_file_reader_sandbox_blocked(file_reader, monkeypatch):
    monkeypatch.setattr(
        "pydeepseek_tui.tools.file_reader.is_path_allowed",
        lambda fp, ad=None: False,
    )

    result = await file_reader.execute(file_path="/etc/passwd")
    assert "Erro de seguranca" in result
