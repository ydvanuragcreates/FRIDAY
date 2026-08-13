from langchain_core.tools import tool

from app.core.command_safety import CommandValidationError, run_validated_command
from app.core.config import get_settings


@tool("run_tests")
def run_tests() -> str:
    """Run the project's configured test suite (TEST_COMMAND, default
    'pytest') inside the workspace and report the exit code plus captured
    stdout/stderr.
    """
    try:
        return run_validated_command(get_settings().test_command)
    except CommandValidationError as exc:
        return f"Error: {exc}"
