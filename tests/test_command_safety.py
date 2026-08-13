import pytest

from app.core.command_safety import (
    CommandValidationError,
    run_validated_command,
    validate_command,
)
from app.core.config import get_settings


@pytest.fixture
def workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_validate_command_accepts_allowed_executable(workspace) -> None:
    assert validate_command("pytest -k auth") == ["pytest", "-k", "auth"]


def test_validate_command_rejects_executable_not_in_allowlist(workspace) -> None:
    with pytest.raises(CommandValidationError, match="not in the allowed command list"):
        validate_command("curl https://example.com")


def test_validate_command_rejects_always_denied_executable(monkeypatch, workspace) -> None:
    monkeypatch.setenv("ALLOWED_COMMANDS", "pytest,rm")
    get_settings.cache_clear()
    with pytest.raises(CommandValidationError, match="never allowed"):
        validate_command("rm -rf .")
    get_settings.cache_clear()


def test_validate_command_rejects_shell_metacharacters(workspace) -> None:
    with pytest.raises(CommandValidationError, match="shell metacharacters"):
        validate_command("pytest; rm -rf /")


def test_validate_command_rejects_inline_exec_flag(workspace) -> None:
    with pytest.raises(CommandValidationError, match="inline code execution"):
        validate_command("python -c print(1)")


def test_validate_command_rejects_traversal_argument(workspace) -> None:
    with pytest.raises(CommandValidationError, match="escapes the workspace"):
        validate_command("pytest ../outside")


def test_validate_command_rejects_absolute_path_argument(workspace) -> None:
    with pytest.raises(CommandValidationError, match="absolute path"):
        validate_command("pytest C:/Windows/System32")


def test_validate_command_rejects_empty_command(workspace) -> None:
    with pytest.raises(CommandValidationError):
        validate_command("   ")


def test_run_validated_command_executes_and_reports_exit_code(workspace) -> None:
    result = run_validated_command("python --version")
    assert result.startswith("Exit code: 0")


def test_run_validated_command_raises_for_invalid_command(workspace) -> None:
    with pytest.raises(CommandValidationError):
        run_validated_command("rm -rf /")
