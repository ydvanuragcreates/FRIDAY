import pytest
from fastapi.testclient import TestClient

from app.indexing.indexer import IndexResult
from app.indexing.vector_store import InvalidProjectIdError
from app.main import app
from app.services.indexing_service import IndexingServiceError, get_indexing_service


class _FakeIndexingService:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def index_project(self, project_id, path="."):
        if self._error:
            raise self._error
        return self._result


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_index_project_returns_result_on_success(client: TestClient) -> None:
    fake_result = IndexResult(
        project_id="demo", collection_name="code_demo", files_indexed=3, chunks_indexed=12, errors=[]
    )
    app.dependency_overrides[get_indexing_service] = lambda: _FakeIndexingService(result=fake_result)

    response = client.post("/api/projects/demo/index", json={"path": "."})

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "demo"
    assert body["collection_name"] == "code_demo"
    assert body["files_indexed"] == 3
    assert body["chunks_indexed"] == 12


def test_index_project_uses_default_path_when_body_omitted(client: TestClient) -> None:
    fake_result = IndexResult(project_id="demo", collection_name="code_demo", files_indexed=0, chunks_indexed=0)
    app.dependency_overrides[get_indexing_service] = lambda: _FakeIndexingService(result=fake_result)

    response = client.post("/api/projects/demo/index", json={})

    assert response.status_code == 200


def test_index_project_returns_400_for_invalid_project_id(client: TestClient) -> None:
    app.dependency_overrides[get_indexing_service] = lambda: _FakeIndexingService(
        error=InvalidProjectIdError("bad project id")
    )

    response = client.post("/api/projects/bad id!/index", json={})

    assert response.status_code == 400


def test_index_project_returns_502_on_service_error(client: TestClient) -> None:
    app.dependency_overrides[get_indexing_service] = lambda: _FakeIndexingService(
        error=IndexingServiceError("embedding provider unavailable")
    )

    response = client.post("/api/projects/demo/index", json={})

    assert response.status_code == 502
    assert "embedding provider unavailable" in response.json()["detail"]
