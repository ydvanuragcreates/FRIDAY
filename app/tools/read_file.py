from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.workspace import WorkspacePathError, resolve_workspace_path

MAX_READ_CHARS = 20_000


class ReadFileInput(BaseModel):
    file_path: str = Field(
        description="Path to the file to read, relative to the workspace root."
    )


@tool("read_file", args_schema=ReadFileInput)
def read_file(file_path: str) -> str:
    """Read the contents of a single text file inside the workspace.
    Use list_files or search_code first to find the right path.
    """
    try:
        target = resolve_workspace_path(file_path)
    except WorkspacePathError as exc:
        return f"Error: {exc}"

    if not target.exists():
        return f"Error: '{file_path}' does not exist in the workspace"
    if target.is_dir():
        return f"Error: '{file_path}' is a directory, not a file"

    try:
        raw = target.read_bytes()
    except OSError as exc:
        return f"Error: could not read '{file_path}': {exc}"

    if b"\x00" in raw[:8192]:
        return f"Error: '{file_path}' looks like a binary file and can't be displayed"

    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n... (truncated, file exceeds {MAX_READ_CHARS} characters)"
    return text
