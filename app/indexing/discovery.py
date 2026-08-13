from pathlib import Path

from app.core.workspace import get_workspace_root, iter_workspace_files
from app.indexing.languages import LANGUAGE_BY_EXTENSION

# Skip anything bigger than this — a pathologically large file (a lockfile,
# a bundled vendor blob, a data dump) isn't useful to chunk and embed, and
# reading it fully would be wasteful.
MAX_INDEXABLE_FILE_BYTES = 500_000


def discover_source_files(start: Path) -> list[Path]:
    """Recursively find indexable source files under `start`.

    Reuses `iter_workspace_files` (app/core/workspace.py), which already
    skips noise directories (.git, node_modules, __pycache__, ...) and
    never follows symlinks — the same containment guarantees every other
    tool in this project relies on. Filters down to known source
    extensions and a max file size so binaries/lockfiles/vendor blobs
    don't get indexed.
    """
    files: list[Path] = []
    for path in iter_workspace_files(start):
        if path.suffix.lower() not in LANGUAGE_BY_EXTENSION:
            continue
        try:
            if path.stat().st_size > MAX_INDEXABLE_FILE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def relative_posix_path(path: Path) -> str:
    """`path` relative to the workspace root, rendered with forward
    slashes regardless of platform — used as the stable file_path stored
    in chunk metadata.
    """
    root = get_workspace_root()
    return str(path.relative_to(root)).replace("\\", "/")
