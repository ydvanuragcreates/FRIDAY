import re
from dataclasses import dataclass

from app.indexing.parsing import CodeUnit

# Bound on a single chunk's character length — big enough to give an
# embedding model real context, small enough to keep chunks focused and
# retrieval results readable.
MAX_CHUNK_CHARS = 4000

# Overlap (in lines) between consecutive pieces when a single unit or
# fallback region has to be split into multiple chunks, so a boundary
# doesn't sever a thought mid-way with no shared context on either side.
CHUNK_OVERLAP_LINES = 10

# Cap, in lines, on fallback chunks (module-level code not inside any
# parsed unit, or whole files in languages with no parser) — keeps those
# chunks focused even when they're well under MAX_CHUNK_CHARS.
FALLBACK_CHUNK_LINES = 60


@dataclass
class CodeChunk:
    """One retrievable unit of code plus the metadata needed to cite and
    re-locate it: file path, language, module, and the enclosing
    function/class if the chunk came from one.
    """

    chunk_id: str
    file_path: str
    language: str
    module: str
    symbol: str | None
    symbol_type: str | None
    start_line: int
    end_line: int
    content: str


def derive_module(file_path: str) -> str:
    """A dotted module-ish label derived from the file path, e.g.
    'app/core/config.py' -> 'app.core.config'.
    """
    without_extension = re.sub(r"\.[^./]+$", "", file_path)
    return without_extension.replace("/", ".")


def _split_lines(lines: list[str], start_line: int, max_lines: int | None = None) -> list[tuple[int, int, str]]:
    """Split `lines` (already known to start at `start_line`, 1-indexed)
    into pieces bounded by MAX_CHUNK_CHARS and, if given, `max_lines`.
    Returns (start_line, end_line, content) tuples, each inclusive.

    Grows each piece greedily line-by-line against the actual running
    length, rather than pre-computing a fixed lines-per-chunk from the
    unit's *average* line length — line length within a unit is rarely
    uniform, and an average-based estimate can walk a piece past
    MAX_CHUNK_CHARS whenever the tail runs longer than the head.
    """
    n = len(lines)
    if n == 0:
        return []

    full_content = "\n".join(lines)
    if len(full_content) <= MAX_CHUNK_CHARS and (max_lines is None or n <= max_lines):
        return [(start_line, start_line + n - 1, full_content)]

    pieces: list[tuple[int, int, str]] = []
    i = 0
    while i < n:
        j = i + 1
        length = len(lines[i])
        while j < n:
            next_length = length + 1 + len(lines[j])  # +1 for the joining newline
            if next_length > MAX_CHUNK_CHARS or (max_lines is not None and j - i + 1 > max_lines):
                break
            length = next_length
            j += 1

        piece_lines = lines[i:j]
        piece_start = start_line + i
        piece_end = piece_start + len(piece_lines) - 1
        pieces.append((piece_start, piece_end, "\n".join(piece_lines)))

        if j >= n:
            break
        i += max(1, (j - i) - CHUNK_OVERLAP_LINES)
    return pieces


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    merged = [list(sorted(intervals)[0])]
    for start, end in sorted(intervals)[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def _gaps(covered: list[tuple[int, int]], total_lines: int) -> list[tuple[int, int]]:
    gaps: list[tuple[int, int]] = []
    cursor = 1
    for start, end in covered:
        if start > cursor:
            gaps.append((cursor, start - 1))
        cursor = max(cursor, end + 1)
    if cursor <= total_lines:
        gaps.append((cursor, total_lines))
    return gaps


def _make_chunk(
    file_path: str,
    language: str,
    module: str,
    symbol: str | None,
    symbol_type: str | None,
    start_line: int,
    end_line: int,
    content: str,
) -> CodeChunk:
    chunk_id = f"{file_path}:{start_line}-{end_line}:{symbol or 'module'}"
    return CodeChunk(
        chunk_id=chunk_id,
        file_path=file_path,
        language=language,
        module=module,
        symbol=symbol,
        symbol_type=symbol_type,
        start_line=start_line,
        end_line=end_line,
        content=content,
    )


def chunk_file(file_path: str, language: str, text: str, units: list[CodeUnit]) -> list[CodeChunk]:
    """Turn one file's text (plus whatever function/class units were
    already parsed out of it) into CodeChunks.

    Every parsed unit becomes its own chunk (split further if it's too
    big). Whatever lines aren't covered by any unit — imports, constants,
    top-level statements, or the entire file for languages with no
    parser — become separate fallback chunks via a fixed-size sliding
    window. A class's chunk and its methods' chunks do overlap in content
    by design: multi-granularity retrieval (the whole class for "how is
    X structured", a single method for "how does X.foo work") is more
    useful here than deduplicating.
    """
    lines = text.splitlines()
    if not lines:
        return []

    module = derive_module(file_path)
    chunks: list[CodeChunk] = []

    for unit in units:
        unit_lines = lines[unit.start_line - 1 : unit.end_line]
        for start, end, content in _split_lines(unit_lines, unit.start_line):
            if content.strip():
                chunks.append(
                    _make_chunk(file_path, language, module, unit.symbol, unit.symbol_type, start, end, content)
                )

    covered = _merge_intervals([(u.start_line, u.end_line) for u in units])
    for gap_start, gap_end in _gaps(covered, len(lines)):
        gap_lines = lines[gap_start - 1 : gap_end]
        for start, end, content in _split_lines(gap_lines, gap_start, max_lines=FALLBACK_CHUNK_LINES):
            if content.strip():
                chunks.append(_make_chunk(file_path, language, module, None, None, start, end, content))

    return chunks
