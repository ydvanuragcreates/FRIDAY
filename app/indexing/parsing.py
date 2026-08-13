"""Turn a file's text into a list of CodeUnit spans (function/class
boundaries with 1-indexed, inclusive line numbers).

Deliberately not a full parser for every language — that's what
tree-sitter is for, at the cost of a native-build dependency this project
avoids (see app/indexing/languages.py). Python gets exact boundaries via
the stdlib `ast` module; brace-delimited languages (JS/TS/Java/Go/Rust/...)
get a regex-plus-brace-counting heuristic that's good enough for chunk
boundaries, not a guarantee of correctness on every edge case (nested
template literals, multi-line strings containing braces, etc. can throw
it off by a few lines). Anything else — and any file where a parser finds
nothing — falls back to plain sliding-window chunking in chunking.py,
which needs no units at all.
"""

import ast
import re
from dataclasses import dataclass

from app.indexing.languages import BRACE_DELIMITED_LANGUAGES


@dataclass
class CodeUnit:
    symbol: str
    symbol_type: str  # "function" | "method" | "class"
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive


def _python_node_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", None)
    if decorators:
        return decorators[0].lineno
    return node.lineno


def parse_python_units(text: str) -> list[CodeUnit]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []

    units: list[CodeUnit] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            units.append(
                CodeUnit(
                    symbol=node.name,
                    symbol_type="function",
                    start_line=_python_node_start(node),
                    end_line=node.end_lineno or node.lineno,
                )
            )
        elif isinstance(node, ast.ClassDef):
            units.append(
                CodeUnit(
                    symbol=node.name,
                    symbol_type="class",
                    start_line=_python_node_start(node),
                    end_line=node.end_lineno or node.lineno,
                )
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    units.append(
                        CodeUnit(
                            symbol=f"{node.name}.{child.name}",
                            symbol_type="method",
                            start_line=_python_node_start(child),
                            end_line=child.end_lineno or child.lineno,
                        )
                    )

    units.sort(key=lambda u: u.start_line)
    return units


# (pattern, symbol_type) — first match on a line wins. Approximate on
# purpose: good enough to find likely symbol-start lines across a broad
# swath of C-like languages without a dedicated parser per language.
_BRACE_SYMBOL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s+(\w+)\s*\("), "function"),
    (
        re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::[^=]+)?=>"
        ),
        "function",
    ),
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)"), "class"),
    (re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\("), "function"),
    (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)"), "function"),
    # ES6 method shorthand (also covers constructor/get/set/static/async
    # methods) — no return-type token, unlike the java/csharp pattern
    # below, so it has to come first or the two would never both match.
    (re.compile(r"^\s*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?(\w+)\s*\([^;{]*\)\s*\{\s*$"), "method"),
    (
        re.compile(
            r"^\s*(?:public|private|protected|internal|static|final|override|virtual|async|\s)+"
            r"[\w<>\[\],\.]+\s+(\w+)\s*\([^;{]*\)\s*\{?\s*$"
        ),
        "method",
    ),
]

_EXCLUDED_SYMBOL_NAMES = {
    "if", "for", "while", "switch", "catch", "return", "else", "do", "try", "with",
}


def _find_block_end(lines: list[str], start_idx: int) -> int:
    """Given the 0-indexed line a symbol's signature starts on, find the
    0-indexed line its closing brace is on via naive depth counting
    (line comments stripped, strings not accounted for).
    """
    depth = 0
    opened = False
    for idx in range(start_idx, len(lines)):
        code_part = lines[idx].split("//", 1)[0]
        depth += code_part.count("{") - code_part.count("}")
        if "{" in code_part:
            opened = True
        if opened and depth <= 0:
            return idx
    return len(lines) - 1


def _scan_brace_units(lines: list[str], start_idx: int, end_idx: int) -> list[CodeUnit]:
    """Scan lines[start_idx:end_idx] for symbol-start lines. A matched
    block's own lines are skipped (not re-scanned) EXCEPT for "class"
    blocks, whose body is recursed into for method-level units — a flat
    scan alone would only ever find top-level symbols, missing every
    method inside every class.
    """
    units: list[CodeUnit] = []
    i = start_idx
    while i < end_idx:
        matched = None
        for pattern, symbol_type in _BRACE_SYMBOL_PATTERNS:
            m = pattern.match(lines[i])
            if m and m.group(1) not in _EXCLUDED_SYMBOL_NAMES:
                matched = (m.group(1), symbol_type)
                break

        if matched is None:
            i += 1
            continue

        symbol, symbol_type = matched
        block_end = _find_block_end(lines, i)
        units.append(
            CodeUnit(symbol=symbol, symbol_type=symbol_type, start_line=i + 1, end_line=block_end + 1)
        )

        if symbol_type == "class":
            for nested in _scan_brace_units(lines, i + 1, block_end):
                nested.symbol = f"{symbol}.{nested.symbol}"
                nested.symbol_type = "method"
                units.append(nested)

        i = block_end + 1

    return units


def parse_brace_language_units(text: str) -> list[CodeUnit]:
    lines = text.splitlines()
    return _scan_brace_units(lines, 0, len(lines))


def parse_code_units(language: str, text: str) -> list[CodeUnit]:
    """Dispatch to the right parsing strategy for `language`. Returns an
    empty list (not an error) for languages with no specific parser —
    the whole file then becomes fallback sliding-window chunks.
    """
    if language == "python":
        return parse_python_units(text)
    if language in BRACE_DELIMITED_LANGUAGES:
        return parse_brace_language_units(text)
    return []
