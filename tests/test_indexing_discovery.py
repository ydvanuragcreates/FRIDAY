import pytest

from app.core.config import get_settings
from app.indexing.discovery import MAX_INDEXABLE_FILE_BYTES, discover_source_files, relative_posix_path


@pytest.fixture
def workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_discover_source_files_finds_known_extensions(workspace) -> None:
    (workspace / "main.py").write_text("print(1)\n")
    (workspace / "app.js").write_text("console.log(1);\n")
    (workspace / "notes.txt").write_text("not source code\n")

    found = {relative_posix_path(p) for p in discover_source_files(workspace)}

    assert "main.py" in found
    assert "app.js" in found
    assert "notes.txt" not in found


def test_discover_source_files_skips_noise_directories(workspace) -> None:
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "dep.js").write_text("module.exports = {};\n")
    (workspace / "real.js").write_text("console.log(1);\n")

    found = {relative_posix_path(p) for p in discover_source_files(workspace)}

    assert "real.js" in found
    assert not any("node_modules" in f for f in found)


def test_discover_source_files_skips_oversized_files(workspace) -> None:
    (workspace / "huge.py").write_text("x = 1\n" * (MAX_INDEXABLE_FILE_BYTES // 4))
    (workspace / "small.py").write_text("x = 1\n")

    found = {relative_posix_path(p) for p in discover_source_files(workspace)}

    assert "small.py" in found
    assert "huge.py" not in found


def test_relative_posix_path_uses_forward_slashes(workspace) -> None:
    nested = workspace / "pkg" / "mod.py"
    nested.parent.mkdir()
    nested.write_text("x = 1\n")

    assert relative_posix_path(nested) == "pkg/mod.py"
