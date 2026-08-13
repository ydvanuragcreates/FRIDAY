from app.core.diff import unified_file_diff


def test_unified_file_diff_reports_no_changes_for_identical_content() -> None:
    result = unified_file_diff("a.py", "print(1)\n", "print(1)\n")
    assert result == "(no changes)"


def test_unified_file_diff_shows_additions_and_removals() -> None:
    result = unified_file_diff("a.py", "print(1)\n", "print(2)\n")
    assert "-print(1)" in result
    assert "+print(2)" in result
    assert "a/a.py" in result
    assert "b/a.py" in result


def test_unified_file_diff_handles_new_file_from_empty_content() -> None:
    result = unified_file_diff("new.py", "", "print('hi')\n")
    assert "+print('hi')" in result
