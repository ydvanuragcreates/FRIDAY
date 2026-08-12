import pytest

from app.core.config import get_settings
from app.tools.list_files import list_files
from app.tools.read_file import read_file
from app.tools.search_code import search_code


@pytest.fixture
def workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "auth.py").write_text("def login():\n    pass\n")
    (tmp_path / "app" / "main.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# Demo\n")

    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    yield tmp_path

    get_settings.cache_clear()


def test_list_files_lists_everything_recursively(workspace) -> None:
    result = list_files.invoke({"directory": "."})
    assert "app/auth.py" in result
    assert "app/main.py" in result
    assert "README.md" in result


def test_list_files_rejects_traversal(workspace) -> None:
    result = list_files.invoke({"directory": "../"})
    assert result.startswith("Error:")


def test_list_files_reports_missing_directory(workspace) -> None:
    result = list_files.invoke({"directory": "does_not_exist"})
    assert result.startswith("Error:")


def test_read_file_returns_contents(workspace) -> None:
    result = read_file.invoke({"file_path": "app/auth.py"})
    assert "def login" in result


def test_read_file_rejects_missing_file(workspace) -> None:
    result = read_file.invoke({"file_path": "does_not_exist.py"})
    assert result.startswith("Error:")


def test_read_file_rejects_traversal(workspace) -> None:
    result = read_file.invoke({"file_path": "../outside.txt"})
    assert result.startswith("Error:")


def test_read_file_rejects_directory(workspace) -> None:
    result = read_file.invoke({"file_path": "app"})
    assert result.startswith("Error:")


def test_search_code_finds_matching_line(workspace) -> None:
    result = search_code.invoke({"query": "login", "file_pattern": "*.py"})
    assert "app/auth.py" in result
    assert "def login" in result


def test_search_code_respects_file_pattern(workspace) -> None:
    result = search_code.invoke({"query": "Demo", "file_pattern": "*.py"})
    assert "No matches" in result


def test_search_code_no_matches(workspace) -> None:
    result = search_code.invoke({"query": "nonexistent_symbol_xyz"})
    assert result.startswith("No matches")
