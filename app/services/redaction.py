"""Best-effort scrubbing of secret-looking content before it's persisted
as tool_call input/output. Not a guarantee — a secret shaped differently
than anything here can still slip through — but it catches the realistic
case this project actually has: read_file returning a .env file's
contents verbatim, or a command's output echoing an API key.
"""

import re
from typing import Any

REDACTED_PLACEHOLDER = "***REDACTED***"

# Known provider API-key shapes.
_SECRET_TOKEN_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}"),  # Anthropic
    re.compile(r"pa-[A-Za-z0-9\-_]{10,}"),  # Voyage AI
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # generic OpenAI-style
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),  # GitHub personal access token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # Google API key
]

# `KEY=value` / `export KEY=value` lines where the key name suggests a
# secret — covers .env-style file contents and shell output alike.
_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"(?im)^(\s*(?:export\s+)?[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PWD)[A-Z0-9_]*\s*=\s*)(\S+)"
)

# Filenames that are almost always secrets regardless of content shape —
# their entire content gets replaced rather than pattern-matched.
_SECRET_FILENAME_PATTERN = re.compile(r"(?i)(^|[\\/])\.env(\.[a-z0-9]+)?$|\.(pem|key|p12|pfx)$")


def redact_text(text: str) -> str:
    if not text:
        return text
    redacted = _ENV_ASSIGNMENT_PATTERN.sub(rf"\1{REDACTED_PLACEHOLDER}", text)
    for pattern in _SECRET_TOKEN_PATTERNS:
        redacted = pattern.sub(REDACTED_PLACEHOLDER, redacted)
    return redacted


def looks_like_secret_file(file_path: str) -> bool:
    return bool(_SECRET_FILENAME_PATTERN.search(file_path))


def redact_tool_io(args: dict[str, Any], output: str) -> tuple[dict[str, Any], str]:
    """Redact a tool call's args/output before persistence.

    A `file_path`/`path` argument that looks like a secrets file gets its
    whole output replaced outright — a real secret's *value* might not
    match any known token shape, but the fact that it came from a `.env`
    file is itself the signal.
    """
    file_path = args.get("file_path") or args.get("path") if isinstance(args, dict) else None
    if file_path and looks_like_secret_file(str(file_path)):
        return args, "[redacted: this file looks like it may contain secrets]"

    redacted_output = redact_text(output)
    redacted_args = (
        {k: (redact_text(v) if isinstance(v, str) else v) for k, v in args.items()}
        if isinstance(args, dict)
        else args
    )
    return redacted_args, redacted_output
