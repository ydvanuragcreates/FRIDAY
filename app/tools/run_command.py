from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.command_safety import CommandValidationError, run_validated_command


class RunCommandInput(BaseModel):
    command: str = Field(
        description=(
            "A single allowlisted command to run inside the workspace, e.g. "
            "'pytest -k auth' or 'npm run build'. Must not contain shell "
            "operators like ;, &&, |, or redirection — pass a plain "
            "program-and-arguments string."
        )
    )


@tool("run_command", args_schema=RunCommandInput)
def run_command(command: str) -> str:
    """Run a validated, allowlisted, non-interactive command inside the
    workspace (e.g. a linter, a build step, or a version check). The
    executable must be on the configured allowlist; destructive or
    unlisted commands are rejected outright rather than executed.
    """
    try:
        return run_validated_command(command)
    except CommandValidationError as exc:
        return f"Error: {exc}"
