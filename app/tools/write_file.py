from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.workspace import WorkspacePathError, resolve_workspace_path


class WriteFileInput(BaseModel):
    file_path: str = Field(
        description="Path of the file to create or overwrite, relative to the workspace root."
    )
    content: str = Field(description="Full new text content of the file.")


@tool("write_file", args_schema=WriteFileInput)
def write_file(file_path: str, content: str) -> str:
    """Create or overwrite a file inside the workspace with new content.

    Overwriting an existing file is destructive — the previous content is
    lost — which is why this tool is never wired into the free-roaming
    investigation loop. It's only ever invoked (a) to compute a diff for
    human review, without touching disk, or (b) to actually apply a change
    that a human has already approved.
    """
    try:
        target = resolve_workspace_path(file_path)
    except WorkspacePathError as exc:
        return f"Error: {exc}"

    if target.exists() and target.is_dir():
        return f"Error: '{file_path}' is a directory, not a file"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Error: could not write '{file_path}': {exc}"

    return f"Wrote '{file_path}' ({len(content)} characters)"
