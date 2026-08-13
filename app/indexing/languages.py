"""Extension-based language detection.

Good enough for chunk metadata and for picking a parsing strategy — this
project deliberately avoids a full multi-language AST toolchain (e.g.
tree-sitter) to stay dependency-light and avoid native builds; see
app/indexing/parsing.py for how each language family is actually parsed.
"""

from pathlib import PurePosixPath

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
}

# Language families whose block structure is brace-delimited, so
# parsing.BraceLanguageParser's brace-counting heuristic applies.
BRACE_DELIMITED_LANGUAGES = {
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "c",
    "cpp",
    "csharp",
    "php",
    "kotlin",
    "scala",
}


def detect_language(file_name: str) -> str:
    """Return a language label for `file_name` based on its extension,
    or "unknown" if unrecognized.
    """
    suffix = PurePosixPath(file_name.replace("\\", "/")).suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(suffix, "unknown")
