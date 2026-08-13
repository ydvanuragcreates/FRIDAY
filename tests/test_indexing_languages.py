from app.indexing.languages import detect_language


def test_detect_language_recognizes_common_extensions() -> None:
    assert detect_language("app/core/config.py") == "python"
    assert detect_language("src/index.ts") == "typescript"
    assert detect_language("main.go") == "go"
    assert detect_language("lib.rs") == "rust"
    assert detect_language("Program.cs") == "csharp"


def test_detect_language_is_case_insensitive_on_extension() -> None:
    assert detect_language("Module.PY") == "python"


def test_detect_language_handles_windows_style_paths() -> None:
    assert detect_language("app\\core\\config.py") == "python"


def test_detect_language_returns_unknown_for_unrecognized_extension() -> None:
    assert detect_language("data.bin") == "unknown"
    assert detect_language("no_extension") == "unknown"
