from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.workspace import (
    WorkspacePathError,
    get_workspace_root,
    iter_workspace_files,
    resolve_workspace_path,
)

MAX_LISTED_FILES = 300


class ListFilesInput(BaseModel):
    directory: str = Field(
        default=".",
        description=(
            "Directory to list, relative to the workspace root. "
            "Use '.' to list the entire workspace."
        ),
    )


@tool("list_files", args_schema=ListFilesInput)
def list_files(directory: str = ".") -> str:
    """List files inside the workspace (recursively), relative to the
    workspace root. Use this first to discover what's in the project
    before reading or searching specific files.
    """
    try:
        target = resolve_workspace_path(directory)
    except WorkspacePathError as exc:
        return f"Error: {exc}"

    if not target.exists():
        return f"Error: '{directory}' does not exist in the workspace"
    if not target.is_dir():
        return f"Error: '{directory}' is not a directory"

    root = get_workspace_root()
    paths = sorted(
        str(p.relative_to(root)).replace("\\", "/") for p in iter_workspace_files(target)
    )

    if not paths:
        return f"No files found under '{directory}'"

    truncated = len(paths) > MAX_LISTED_FILES
    paths = paths[:MAX_LISTED_FILES]
    result = "\n".join(paths)
    if truncated:
        result += f"\n... ({MAX_LISTED_FILES}+ files, list truncated)"
    return result
