from app.indexing.chunking import MAX_CHUNK_CHARS, chunk_file, derive_module
from app.indexing.parsing import CodeUnit


def test_derive_module_converts_path_to_dotted_form() -> None:
    assert derive_module("app/core/config.py") == "app.core.config"


def test_derive_module_handles_root_level_file() -> None:
    assert derive_module("main.py") == "main"


def test_chunk_file_returns_empty_list_for_empty_text() -> None:
    assert chunk_file("empty.py", "python", "", []) == []


def test_chunk_file_creates_one_chunk_per_small_unit() -> None:
    text = "import os\n\n\ndef foo():\n    return 1\n"
    units = [CodeUnit(symbol="foo", symbol_type="function", start_line=4, end_line=5)]

    chunks = chunk_file("m.py", "python", text, units)

    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["foo"].content == "def foo():\n    return 1"
    assert by_symbol["foo"].symbol_type == "function"
    assert by_symbol["foo"].file_path == "m.py"
    assert by_symbol["foo"].module == "m"


def test_chunk_file_captures_leftover_lines_as_module_level_chunk() -> None:
    text = "import os\nimport sys\n\ndef foo():\n    return 1\n"
    units = [CodeUnit(symbol="foo", symbol_type="function", start_line=4, end_line=5)]

    chunks = chunk_file("m.py", "python", text, units)

    module_chunks = [c for c in chunks if c.symbol is None]
    assert len(module_chunks) == 1
    assert "import os" in module_chunks[0].content
    assert "import sys" in module_chunks[0].content


def test_chunk_file_splits_oversized_unit_with_overlap() -> None:
    body_lines = [f"    x{i} = {i}" for i in range(400)]
    text = "def big():\n" + "\n".join(body_lines) + "\n"
    units = [CodeUnit(symbol="big", symbol_type="function", start_line=1, end_line=401)]

    chunks = chunk_file("m.py", "python", text, units)
    big_chunks = [c for c in chunks if c.symbol == "big"]

    assert len(big_chunks) > 1
    for c in big_chunks:
        assert len(c.content) <= MAX_CHUNK_CHARS
    # consecutive pieces should overlap by roughly CHUNK_OVERLAP_LINES lines
    assert big_chunks[1].start_line <= big_chunks[0].end_line


def test_chunk_file_with_no_units_falls_back_to_sliding_window() -> None:
    text = "\n".join(f"line {i}" for i in range(150))
    chunks = chunk_file("notes.md", "markdown", text, [])

    assert len(chunks) > 1
    assert all(c.symbol is None for c in chunks)
    assert all(c.file_path == "notes.md" for c in chunks)


def test_chunk_file_skips_blank_gap_regions() -> None:
    text = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
    units = [
        CodeUnit(symbol="foo", symbol_type="function", start_line=1, end_line=2),
        CodeUnit(symbol="bar", symbol_type="function", start_line=5, end_line=6),
    ]

    chunks = chunk_file("m.py", "python", text, units)

    assert all(c.symbol is not None for c in chunks)
