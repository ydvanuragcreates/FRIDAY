from functools import lru_cache

from app.indexing.embeddings import EmbeddingProviderError
from app.indexing.factory import get_indexer
from app.indexing.indexer import IndexResult
from app.indexing.vector_store import InvalidProjectIdError


class IndexingServiceError(Exception):
    """Raised when the indexing pipeline fails outright (not a per-file
    error, which is collected into IndexResult.errors instead).
    """


class IndexingService:
    """Thin wrapper around CodebaseIndexer, mirroring AgentService's role
    for the coding-agent graph: keeps pipeline construction and error
    translation out of the routes.

    Deliberately doesn't build the indexer (and its embedding provider)
    until `index_project` is actually called — building it eagerly in
    `__init__` would mean a missing VOYAGE_API_KEY raises from inside the
    FastAPI dependency itself (an unhandled 500) instead of the try/except
    below (a clean 502 with a message).
    """

    def index_project(self, project_id: str, path: str = ".") -> IndexResult:
        try:
            indexer = get_indexer()
            return indexer.index_path(project_id, subpath=path)
        except InvalidProjectIdError:
            raise
        except EmbeddingProviderError as exc:
            raise IndexingServiceError(str(exc)) from exc
        except Exception as exc:
            raise IndexingServiceError(f"Indexing failed: {exc}") from exc


@lru_cache
def get_indexing_service() -> IndexingService:
    return IndexingService()
