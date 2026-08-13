import hashlib

import pytest

from app.core.config import get_settings
from app.indexing.indexer import CodebaseIndexer
from app.indexing.retriever import CodeRetriever, ProjectNotIndexedError
from app.indexing.vector_store import VectorStore


class FakeEmbeddingProvider:
    """Deterministic, offline stand-in for VoyageEmbeddingProvider — hashes
    text into a fixed-size vector. Not semantically meaningful, but lets
    the indexer/retriever/store wiring be tested end-to-end without a
    network call.
    """

    dimensions = 8

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[: self.dimensions]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "auth.py").write_text(
        "def login(user, password):\n    return check_credentials(user, password)\n"
    )
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def indexer() -> CodebaseIndexer:
    return CodebaseIndexer(VectorStore(path=":memory:"), FakeEmbeddingProvider())


def test_index_path_indexes_all_discovered_files(workspace, indexer: CodebaseIndexer) -> None:
    result = indexer.index_path("testproj")

    assert result.project_id == "testproj"
    assert result.collection_name == "code_testproj"
    assert result.files_indexed == 2
    assert result.chunks_indexed > 0
    assert result.errors == []


def test_index_path_reports_error_for_missing_subpath(workspace, indexer: CodebaseIndexer) -> None:
    result = indexer.index_path("testproj", subpath="does_not_exist")

    assert result.files_indexed == 0
    assert result.errors


def test_index_path_reports_error_for_traversal_subpath(workspace, indexer: CodebaseIndexer) -> None:
    result = indexer.index_path("testproj", subpath="../outside")

    assert result.files_indexed == 0
    assert result.errors


def test_retriever_finds_indexed_content(workspace, indexer: CodebaseIndexer) -> None:
    indexer.index_path("testproj")
    retriever = CodeRetriever(indexer._vector_store, indexer._embedding_provider)

    results = retriever.search("testproj", "login credentials", top_k=5)

    assert len(results) > 0
    assert all(r.file_path in ("auth.py", "utils.py") for r in results)


def test_retriever_raises_for_unindexed_project(workspace, indexer: CodebaseIndexer) -> None:
    retriever = CodeRetriever(indexer._vector_store, indexer._embedding_provider)

    with pytest.raises(ProjectNotIndexedError):
        retriever.search("never-indexed", "anything", top_k=5)
