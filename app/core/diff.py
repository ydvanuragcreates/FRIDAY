import difflib


def unified_file_diff(file_path: str, old_content: str, new_content: str) -> str:
    """Render a unified diff of a proposed file change, for human review
    before it's applied to disk.
    """
    diff_lines = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    diff_text = "".join(diff_lines)
    return diff_text if diff_text else "(no changes)"
