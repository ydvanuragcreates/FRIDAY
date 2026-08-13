"""Builds the indexing/retrieval stack from Settings — the one place that
wires VectorStore + EmbeddingProvider together. Still no LangChain/
LangGraph imports; app/tools/semantic_code_search.py and
app/services/indexing_service.py are the callers on either side of the
agent-framework boundary.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.indexing.embeddings import EmbeddingProvider, VoyageEmbeddingProvider
from app.indexing.indexer import CodebaseIndexer
from app.indexing.retriever import CodeRetriever
from app.indexing.vector_store import VectorStore


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    return VectorStore(url=settings.qdrant_url, api_key=settings.qdrant_api_key, path=settings.qdrant_path)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return VoyageEmbeddingProvider(api_key=settings.voyage_api_key, model=settings.embedding_model)


def get_indexer() -> CodebaseIndexer:
    return CodebaseIndexer(get_vector_store(), get_embedding_provider())


def get_retriever() -> CodeRetriever:
    return CodeRetriever(get_vector_store(), get_embedding_provider())
