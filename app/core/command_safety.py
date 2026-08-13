import os
import shlex
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.core.workspace import get_workspace_root

MAX_OUTPUT_CHARS = 10_000

# Executables that are never allowed, regardless of how ALLOWED_COMMANDS is
# configured. There's no way for a single text-based tool call to get
# meaningful per-invocation human sign-off on a command like this, so the
# safe default is to refuse it outright — "requires explicit human
# approval" becomes "requires a human to change the source/config", which
# is a much higher bar than one approve click.
ALWAYS_DENIED_EXECUTABLES = {
    "rm", "rmdir", "del", "erase", "format", "mkfs", "dd",
    "shutdown", "reboot", "poweroff", "halt",
    "taskkill", "kill", "pkill",
    "chmod", "chown", "chgrp", "icacls", "takeown",
    "reg", "regedit", "diskpart", "sudo", "su",
}

# Interpreters that accept an inline-code flag can run arbitrary code
# regardless of the allowlist, defeating its purpose — block those flags
# specifically rather than banning the interpreters entirely (they're
# needed to run test/build commands).
INLINE_EXEC_EXECUTABLES = {"python", "python3", "node", "ruby", "perl"}
INLINE_EXEC_FLAGS = {"-c", "--eval", "-e"}

SHELL_METACHARACTERS = set(";&|<>`$\n\r")


class CommandValidationError(Exception):
    """Raised when a requested command fails validation and must not run."""


def _split(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=(os.name != "nt"))
    except ValueError as exc:
        raise CommandValidationError(f"could not parse command: {exc}") from exc


def validate_command(command: str) -> list[str]:
    """Validate `command` and return its argv, or raise
    CommandValidationError explaining why it was rejected.

    The command is never passed through a shell — argv is executed
    directly — but it's still allowlisted by executable name and checked
    for shell metacharacters, inline-code flags, and path arguments that
    look like they're trying to reach outside the workspace, as defense
    in depth on top of that.
    """
    if not command.strip():
        raise CommandValidationError("command must not be empty")
    if any(ch in command for ch in SHELL_METACHARACTERS):
        raise CommandValidationError(
            "command must not contain shell metacharacters (;, &, |, <, >, `, $)"
        )

    argv = _split(command)
    if not argv:
        raise CommandValidationError("command must not be empty")

    executable_name = Path(argv[0]).name.lower()
    if executable_name.endswith((".exe", ".cmd", ".bat")):
        executable_name = executable_name.rsplit(".", 1)[0]

    if executable_name in ALWAYS_DENIED_EXECUTABLES:
        raise CommandValidationError(f"'{argv[0]}' is never allowed")

    allowed = {
        c.strip().lower() for c in get_settings().allowed_commands.split(",") if c.strip()
    }
    if executable_name not in allowed:
        raise CommandValidationError(
            f"'{argv[0]}' is not in the allowed command list ({sorted(allowed)})"
        )

    if executable_name in INLINE_EXEC_EXECUTABLES:
        if any(arg in INLINE_EXEC_FLAGS for arg in argv[1:]):
            raise CommandValidationError(
                f"inline code execution flags ({sorted(INLINE_EXEC_FLAGS)}) are not allowed"
            )

    for arg in argv[1:]:
        if os.path.isabs(arg):
            raise CommandValidationError(f"absolute path argument '{arg}' is not allowed")
        if ".." in Path(arg).parts:
            raise CommandValidationError(f"path argument '{arg}' escapes the workspace")

    return argv


def _resolve_for_execution(argv: list[str]) -> list[str]:
    """On Windows, .cmd/.bat launchers (e.g. npm.cmd) can't be started
    directly via CreateProcess without a shell. Route just those through
    `cmd /c` — the metacharacter check in validate_command() already ran
    on the original string, so this doesn't reopen shell-injection risk.
    """
    if os.name != "nt":
        return argv
    resolved = shutil.which(argv[0])
    if resolved and resolved.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", *argv]
    return argv


def run_validated_command(command: str) -> str:
    """Validate then run `command` inside the workspace root, with a
    timeout and truncated output.

    Raises CommandValidationError if the command fails validation —
    callers (tool functions) turn that into an "Error: ..." string rather
    than letting it propagate, consistent with how every other tool in
    this project reports failures back to the LLM.
    """
    argv = validate_command(command)
    settings = get_settings()

    try:
        proc = subprocess.run(
            _resolve_for_execution(argv),
            cwd=get_workspace_root(),
            capture_output=True,
            text=True,
            timeout=settings.command_timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {settings.command_timeout_seconds}s"
    except OSError as exc:
        return f"Error: failed to execute command: {exc}"

    stdout = proc.stdout[:MAX_OUTPUT_CHARS]
    stderr = proc.stderr[:MAX_OUTPUT_CHARS]
    if len(proc.stdout) > MAX_OUTPUT_CHARS:
        stdout += "\n... (stdout truncated)"
    if len(proc.stderr) > MAX_OUTPUT_CHARS:
        stderr += "\n... (stderr truncated)"

    return f"Exit code: {proc.returncode}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
