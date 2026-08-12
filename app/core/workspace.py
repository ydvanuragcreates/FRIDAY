import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

from app.core.config import get_settings

# Noise directories we never walk into or list — not source code, and in
# .git's case, potentially sensitive history.
EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


class WorkspacePathError(Exception):
    """Raised when a requested path escapes the configured workspace root."""


def get_workspace_root() -> Path:
    """The absolute, resolved root directory tools are allowed to touch."""
    settings = get_settings()
    return Path(settings.workspace_root).resolve()


def resolve_workspace_path(relative_path: str) -> Path:
    """Resolve `relative_path` against the workspace root and guarantee the
    result stays inside it.

    Absolute paths are rejected outright for a clear, fast error message.
    The real guarantee, though, is the containment check after resolving:
    `.resolve()` collapses `..` segments and follows symlinks to their real
    target, and whatever comes out the other end must still be inside the
    workspace root — regardless of how the input path was spelled (`..`,
    a symlink, a drive-relative Windows path, etc.), an escaped result
    fails this check and is rejected.
    """
    if Path(relative_path).is_absolute():
        raise WorkspacePathError(
            f"'{relative_path}' is an absolute path; only paths relative to "
            "the workspace are allowed"
        )

    root = get_workspace_root()
    candidate = (root / relative_path).resolve()

    if candidate != root and not candidate.is_relative_to(root):
        raise WorkspacePathError(f"'{relative_path}' resolves outside the workspace root")

    return candidate


def iter_workspace_files(start: Path, *, file_glob: str = "*") -> Iterator[Path]:
    """Recursively yield files under `start`, skipping noise directories.

    Never follows symlinks while walking — a symlink planted inside the
    workspace can't be used to walk out of it.
    """
    for dirpath, dirnames, filenames in os.walk(start, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        for filename in filenames:
            if fnmatch.fnmatch(filename, file_glob):
                yield Path(dirpath) / filename
