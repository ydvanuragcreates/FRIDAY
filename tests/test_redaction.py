from app.services.redaction import looks_like_secret_file, redact_text, redact_tool_io


def test_redact_text_masks_env_style_assignment() -> None:
    text = "ANTHROPIC_API_KEY=sk-ant-abc123def456\nOTHER=fine"
    result = redact_text(text)
    assert "sk-ant-abc123def456" not in result
    assert "OTHER=fine" in result


def test_redact_text_masks_known_token_shapes() -> None:
    text = "here is a token: ghp_1234567890abcdef1234567890abcdef1234"
    result = redact_text(text)
    assert "ghp_1234567890abcdef1234567890abcdef1234" not in result


def test_redact_text_leaves_ordinary_text_untouched() -> None:
    text = "def login(user, password):\n    return True\n"
    assert redact_text(text) == text


def test_redact_text_handles_empty_string() -> None:
    assert redact_text("") == ""


def test_looks_like_secret_file_matches_dotenv() -> None:
    assert looks_like_secret_file(".env")
    assert looks_like_secret_file("app/.env")
    assert looks_like_secret_file("config/.env.production")


def test_looks_like_secret_file_matches_key_files() -> None:
    assert looks_like_secret_file("certs/server.pem")
    assert looks_like_secret_file("id_rsa.key")


def test_looks_like_secret_file_does_not_match_normal_source() -> None:
    assert not looks_like_secret_file("app/core/config.py")


def test_redact_tool_io_replaces_whole_output_for_secret_file() -> None:
    args = {"file_path": ".env"}
    _, output = redact_tool_io(args, "ANTHROPIC_API_KEY=sk-ant-verysecret\n")
    assert "sk-ant-verysecret" not in output
    assert "redacted" in output.lower()


def test_redact_tool_io_pattern_redacts_normal_output() -> None:
    args = {"file_path": "app/main.py"}
    redacted_args, output = redact_tool_io(args, "found ANTHROPIC_API_KEY=sk-ant-verysecret in file")
    assert "sk-ant-verysecret" not in output
    assert redacted_args == args
