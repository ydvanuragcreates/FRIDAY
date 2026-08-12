import pytest

from app.core.config import get_settings
from app.core.workspace import WorkspacePathError, resolve_workspace_path


@pytest.fixture
def workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Point WORKSPACE_ROOT at a throwaway directory with a nested file, so
    path-safety tests never touch the real project.
    """
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "app.py").write_text("print('hello')")

    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    yield tmp_path

    get_settings.cache_clear()


def test_resolves_valid_relative_path(workspace) -> None:
    resolved = resolve_workspace_path("src/app.py")
    assert resolved == (workspace / "src" / "app.py").resolve()


def test_root_itself_is_allowed(workspace) -> None:
    resolved = resolve_workspace_path(".")
    assert resolved == workspace.resolve()


def test_rejects_dot_dot_traversal(workspace) -> None:
    with pytest.raises(WorkspacePathError):
        resolve_workspace_path("../outside.txt")


def test_rejects_nested_dot_dot_traversal(workspace) -> None:
    with pytest.raises(WorkspacePathError):
        resolve_workspace_path("src/../../outside.txt")


def test_rejects_absolute_path(workspace, tmp_path_factory) -> None:
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.txt"
    with pytest.raises(WorkspacePathError):
        resolve_workspace_path(str(outside))
