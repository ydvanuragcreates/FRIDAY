import pytest

from app.indexing.chunking import CodeChunk
from app.indexing.vector_store import (
    InvalidProjectIdError,
    VectorStore,
    collection_name_for_project,
    validate_project_id,
)


def _chunk(chunk_id: str, content: str = "def foo(): pass") -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        file_path="app/foo.py",
        language="python",
        module="app.foo",
        symbol="foo",
        symbol_type="function",
        start_line=1,
        end_line=1,
        content=content,
    )


@pytest.fixture
def store() -> VectorStore:
    return VectorStore(path=":memory:")


def test_validate_project_id_accepts_safe_slug() -> None:
    assert validate_project_id("my-project_1") == "my-project_1"


def test_validate_project_id_rejects_unsafe_characters() -> None:
    with pytest.raises(InvalidProjectIdError):
        validate_project_id("../etc/passwd")


def test_collection_name_for_project_prefixes_and_validates() -> None:
    assert collection_name_for_project("demo") == "code_demo"
    with pytest.raises(InvalidProjectIdError):
        collection_name_for_project("bad id!")


def test_ensure_collection_creates_once(store: VectorStore) -> None:
    assert not store.collection_exists("code_demo")
    store.ensure_collection("code_demo", vector_size=4)
    assert store.collection_exists("code_demo")
    store.ensure_collection("code_demo", vector_size=4)  # idempotent, no error


def test_upsert_and_search_round_trips_metadata(store: VectorStore) -> None:
    store.ensure_collection("code_demo", vector_size=4)
    chunk = _chunk("app/foo.py:1-1:foo")
    store.upsert_chunks("code_demo", [chunk], [[1.0, 0.0, 0.0, 0.0]])

    results = store.search("code_demo", [1.0, 0.0, 0.0, 0.0], top_k=5)

    assert len(results) == 1
    result = results[0]
    assert result.chunk_id == "app/foo.py:1-1:foo"
    assert result.file_path == "app/foo.py"
    assert result.symbol == "foo"
    assert result.content == "def foo(): pass"
    assert result.score > 0.99


def test_upsert_same_chunk_id_overwrites_not_duplicates(store: VectorStore) -> None:
    store.ensure_collection("code_demo", vector_size=4)
    chunk = _chunk("app/foo.py:1-1:foo", content="def foo(): pass")
    store.upsert_chunks("code_demo", [chunk], [[1.0, 0.0, 0.0, 0.0]])

    updated_chunk = _chunk("app/foo.py:1-1:foo", content="def foo(): return 1")
    store.upsert_chunks("code_demo", [updated_chunk], [[1.0, 0.0, 0.0, 0.0]])

    results = store.search("code_demo", [1.0, 0.0, 0.0, 0.0], top_k=10)
    assert len(results) == 1
    assert results[0].content == "def foo(): return 1"


def test_search_respects_language_filter(store: VectorStore) -> None:
    store.ensure_collection("code_demo", vector_size=4)
    py_chunk = _chunk("py:1")
    js_chunk = CodeChunk(
        chunk_id="js:1",
        file_path="app/foo.js",
        language="javascript",
        module="app.foo",
        symbol="foo",
        symbol_type="function",
        start_line=1,
        end_line=1,
        content="function foo() {}",
    )
    store.upsert_chunks("code_demo", [py_chunk, js_chunk], [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])

    results = store.search("code_demo", [1.0, 0.0, 0.0, 0.0], top_k=10, language="javascript")

    assert len(results) == 1
    assert results[0].language == "javascript"


def test_upsert_chunks_rejects_mismatched_lengths(store: VectorStore) -> None:
    store.ensure_collection("code_demo", vector_size=4)
    with pytest.raises(ValueError):
        store.upsert_chunks("code_demo", [_chunk("a")], [])


def test_delete_collection_removes_it(store: VectorStore) -> None:
    store.ensure_collection("code_demo", vector_size=4)
    store.delete_collection("code_demo")
    assert not store.collection_exists("code_demo")
