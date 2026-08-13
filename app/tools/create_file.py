from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.workspace import WorkspacePathError, resolve_workspace_path


class CreateFileInput(BaseModel):
    file_path: str = Field(
        description="Path of the new file to create, relative to the workspace root."
    )
    content: str = Field(description="Full text content of the new file.")


@tool("create_file", args_schema=CreateFileInput)
def create_file(file_path: str, content: str) -> str:
    """Create a brand-new file inside the workspace. Fails if the file
    already exists — use write_file to modify an existing file instead.
    """
    try:
        target = resolve_workspace_path(file_path)
    except WorkspacePathError as exc:
        return f"Error: {exc}"

    if target.exists():
        return f"Error: '{file_path}' already exists; use write_file to modify it"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Error: could not create '{file_path}': {exc}"

    return f"Created '{file_path}' ({len(content)} characters)"
