from app.indexing.parsing import parse_brace_language_units, parse_code_units, parse_python_units

PYTHON_SOURCE = '''\
import os

def top_level_function(x):
    return x + 1


class Greeter:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"hello {self.name}"


@decorated
def decorated_function():
    pass
'''


def test_parse_python_units_finds_top_level_function() -> None:
    units = parse_python_units(PYTHON_SOURCE)
    by_symbol = {u.symbol: u for u in units}
    assert "top_level_function" in by_symbol
    assert by_symbol["top_level_function"].symbol_type == "function"


def test_parse_python_units_finds_class_and_methods() -> None:
    units = parse_python_units(PYTHON_SOURCE)
    by_symbol = {u.symbol: u for u in units}
    assert by_symbol["Greeter"].symbol_type == "class"
    assert by_symbol["Greeter.__init__"].symbol_type == "method"
    assert by_symbol["Greeter.greet"].symbol_type == "method"


def test_parse_python_units_includes_decorator_in_span() -> None:
    units = parse_python_units(PYTHON_SOURCE)
    by_symbol = {u.symbol: u for u in units}
    decorated = by_symbol["decorated_function"]
    decorator_line = PYTHON_SOURCE.splitlines().index("@decorated") + 1
    assert decorated.start_line == decorator_line


def test_parse_python_units_returns_empty_list_on_syntax_error() -> None:
    assert parse_python_units("def broken(:\n") == []


JS_SOURCE = """\
function add(a, b) {
    return a + b;
}

const multiply = (a, b) => {
    return a * b;
};

class Calculator {
    compute(a, b) {
        if (a > b) {
            return a;
        }
        return b;
    }
}
"""


def test_parse_brace_language_units_finds_function() -> None:
    units = parse_brace_language_units(JS_SOURCE)
    by_symbol = {u.symbol: u for u in units}
    assert by_symbol["add"].symbol_type == "function"
    assert JS_SOURCE.splitlines()[by_symbol["add"].start_line - 1].startswith("function add")
    assert JS_SOURCE.splitlines()[by_symbol["add"].end_line - 1].strip() == "}"


def test_parse_brace_language_units_finds_arrow_function() -> None:
    units = parse_brace_language_units(JS_SOURCE)
    by_symbol = {u.symbol: u for u in units}
    assert "multiply" in by_symbol


def test_parse_brace_language_units_finds_class() -> None:
    units = parse_brace_language_units(JS_SOURCE)
    by_symbol = {u.symbol: u for u in units}
    assert by_symbol["Calculator"].symbol_type == "class"
    # nested methods are qualified as Class.method and their span should
    # fall fully inside the class's own span
    compute = by_symbol["Calculator.compute"]
    calculator = by_symbol["Calculator"]
    assert compute.symbol_type == "method"
    assert calculator.start_line < compute.start_line
    assert compute.end_line <= calculator.end_line


def test_parse_brace_language_units_does_not_treat_if_as_a_symbol() -> None:
    units = parse_brace_language_units(JS_SOURCE)
    assert all(u.symbol not in ("if", "Calculator.if") for u in units)


def test_parse_code_units_dispatches_python() -> None:
    units = parse_code_units("python", PYTHON_SOURCE)
    assert any(u.symbol == "top_level_function" for u in units)


def test_parse_code_units_dispatches_brace_language() -> None:
    units = parse_code_units("javascript", JS_SOURCE)
    assert any(u.symbol == "add" for u in units)


def test_parse_code_units_returns_empty_for_language_without_parser() -> None:
    assert parse_code_units("markdown", "# Title\n\nSome text.\n") == []


def test_parse_code_units_returns_empty_for_unknown_language() -> None:
    assert parse_code_units("unknown", "whatever content") == []
