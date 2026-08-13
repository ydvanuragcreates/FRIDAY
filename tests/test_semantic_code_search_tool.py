import importlib

import pytest

from app.indexing.embeddings import EmbeddingProviderError
from app.indexing.retriever import ProjectNotIndexedError
from app.indexing.vector_store import RetrievedChunk
from app.tools.semantic_code_search import semantic_code_search

# app/tools/__init__.py does `from app.tools.semantic_code_search import
# semantic_code_search`, which rebinds that name on the `app.tools`
# package to the tool object — shadowing the submodule. `import
# app.tools.semantic_code_search as x` would resolve `x` to the tool, not
# the module, so importlib is used here to get the real module to patch.
tool_module = importlib.import_module("app.tools.semantic_code_search")


class _FakeRetriever:
    def __init__(self, results=None, error=None):
        self._results = results or []
        self._error = error

    def search(self, project_id, query, top_k=5):
        if self._error:
            raise self._error
        return self._results


def test_semantic_code_search_formats_results(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [
        RetrievedChunk(
            chunk_id="a.py:1-2:foo",
            score=0.87,
            file_path="a.py",
            language="python",
            module="a",
            symbol="foo",
            symbol_type="function",
            start_line=1,
            end_line=2,
            content="def foo():\n    return 1",
        )
    ]
    monkeypatch.setattr(tool_module, "get_retriever", lambda: _FakeRetriever(results=results))

    output = semantic_code_search.invoke({"query": "what does foo do"})

    assert "a.py:1-2" in output
    assert "function foo" in output
    assert "def foo():" in output


def test_semantic_code_search_reports_no_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_module, "get_retriever", lambda: _FakeRetriever(results=[]))

    output = semantic_code_search.invoke({"query": "nonexistent concept"})

    assert output.startswith("No semantically matching code found")


def test_semantic_code_search_reports_unindexed_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tool_module,
        "get_retriever",
        lambda: _FakeRetriever(error=ProjectNotIndexedError("project 'default' has not been indexed yet")),
    )

    output = semantic_code_search.invoke({"query": "anything"})

    assert output.startswith("Error:")
    assert "not been indexed" in output


def test_semantic_code_search_reports_embedding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tool_module,
        "get_retriever",
        lambda: _FakeRetriever(error=EmbeddingProviderError("VOYAGE_API_KEY is not configured")),
    )

    output = semantic_code_search.invoke({"query": "anything"})

    assert output.startswith("Error:")
    assert "VOYAGE_API_KEY" in output
