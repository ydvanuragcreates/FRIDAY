from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.workspace import get_workspace_root, iter_workspace_files

MAX_MATCHES = 100


class SearchCodeInput(BaseModel):
    query: str = Field(description="Text to search for (case-insensitive substring match).")
    file_pattern: str = Field(
        default="*",
        description=(
            "Glob pattern to restrict which filenames are searched, "
            "e.g. '*.py'. Defaults to all files."
        ),
    )


@tool("search_code", args_schema=SearchCodeInput)
def search_code(query: str, file_pattern: str = "*") -> str:
    """Search file contents across the workspace for a text query. Returns
    matching file paths, line numbers, and the matching line. Use this to
    locate relevant code before reading full files.
    """
    if not query.strip():
        return "Error: query must not be empty"

    root = get_workspace_root()
    needle = query.lower()
    matches: list[str] = []

    for path in iter_workspace_files(root, file_glob=file_pattern):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue  # skip binary files

        text = raw.decode("utf-8", errors="replace")
        rel = str(path.relative_to(root)).replace("\\", "/")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                matches.append(f"{rel}:{line_no}: {line.strip()}")
                if len(matches) >= MAX_MATCHES:
                    break
        if len(matches) >= MAX_MATCHES:
            break

    if not matches:
        return f"No matches found for '{query}'"

    result = "\n".join(matches)
    if len(matches) >= MAX_MATCHES:
        result += f"\n... (stopped after {MAX_MATCHES} matches)"
    return result
