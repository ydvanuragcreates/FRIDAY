"""Qdrant-backed vector storage — the only place in this project that
imports qdrant_client. No LangChain/LangGraph imports here; this module
doesn't know an agent exists (see README > "Keep the vector store
separate from LangGraph"). app/indexing/indexer.py and retriever.py are
the only callers, and app/tools/semantic_code_search.py is the only place
any of this meets the agent framework.
"""

import re
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.indexing.chunking import CodeChunk

_PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class InvalidProjectIdError(ValueError):
    """Raised when a project_id isn't a safe collection-name slug."""


def validate_project_id(project_id: str) -> str:
    if not _PROJECT_ID_PATTERN.match(project_id):
        raise InvalidProjectIdError(
            f"'{project_id}' is not a valid project_id — use only letters, digits, "
            "'_' and '-' (max 64 characters)"
        )
    return project_id


def collection_name_for_project(project_id: str) -> str:
    return f"code_{validate_project_id(project_id)}"


@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float
    file_path: str
    language: str
    module: str
    symbol: str | None
    symbol_type: str | None
    start_line: int
    end_line: int
    content: str


def _point_id(chunk_id: str) -> str:
    """Qdrant point IDs must be an unsigned int or a UUID. Deriving a
    deterministic UUID from the chunk_id (file_path:lines:symbol) makes
    re-indexing idempotent — re-upserting the same chunk overwrites the
    same point instead of accumulating duplicates.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class VectorStore:
    """Thin wrapper around a Qdrant collection per project. Runs against
    an embedded on-disk (or in-memory) instance by default — no server
    required — or a real Qdrant deployment if `url` is given.
    """

    def __init__(self, url: str | None = None, api_key: str | None = None, path: str | None = None) -> None:
        if url:
            self._client = QdrantClient(url=url, api_key=api_key)
        else:
            self._client = QdrantClient(path=path or ":memory:")

    def collection_exists(self, collection_name: str) -> bool:
        return self._client.collection_exists(collection_name)

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        if not self.collection_exists(collection_name):
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def delete_collection(self, collection_name: str) -> None:
        if self.collection_exists(collection_name):
            self._client.delete_collection(collection_name)

    def upsert_chunks(self, collection_name: str, chunks: list[CodeChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must be the same length")
        if not chunks:
            return

        points = [
            PointStruct(
                id=_point_id(chunk.chunk_id),
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "module": chunk.module,
                    "symbol": chunk.symbol,
                    "symbol_type": chunk.symbol_type,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                },
            )
            for chunk, vector in zip(chunks, embeddings)
        ]
        self._client.upsert(collection_name=collection_name, points=points)

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        language: str | None = None,
    ) -> list[RetrievedChunk]:
        query_filter = None
        if language:
            query_filter = Filter(must=[FieldCondition(key="language", match=MatchValue(value=language))])

        result = self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
        )

        return [
            RetrievedChunk(
                chunk_id=point.payload["chunk_id"],
                score=point.score,
                file_path=point.payload["file_path"],
                language=point.payload["language"],
                module=point.payload["module"],
                symbol=point.payload["symbol"],
                symbol_type=point.payload["symbol_type"],
                start_line=point.payload["start_line"],
                end_line=point.payload["end_line"],
                content=point.payload["content"],
            )
            for point in result.points
        ]
