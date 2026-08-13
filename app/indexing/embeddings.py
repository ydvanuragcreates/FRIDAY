"""Embedding provider abstraction — deliberately just this module's own
Protocol plus a thin Voyage AI client wrapper. No LangChain/LangGraph
imports here (see README > "Keep the vector store separate from
LangGraph"): app/tools/semantic_code_search.py is the only place this
package meets the agent framework.
"""

from typing import Protocol

import voyageai

# Voyage batches embedding requests server-side; keep well under its
# per-request text-count limit rather than sending thousands at once.
EMBED_BATCH_SIZE = 128


class EmbeddingProvider(Protocol):
    """Anything that can turn text into vectors for storage in / query
    against the vector store. `embed_documents` and `embed_query` are
    kept separate because some providers (Voyage included) tune the
    embedding differently for indexed content vs. a search query.
    """

    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingProviderError(Exception):
    """Raised when an embedding request can't be fulfilled (missing API
    key, provider error, etc.).
    """


# Known output dimensionality per Voyage model, so the vector store's
# collection can be sized correctly without an extra round-trip call.
_VOYAGE_MODEL_DIMENSIONS = {
    "voyage-code-3": 1024,
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "voyage-large-2": 1536,
}


class VoyageEmbeddingProvider:
    """Embeddings via Voyage AI — Anthropic's recommended embeddings
    partner (Claude itself has no embeddings endpoint), and voyage-code-3
    specifically is trained for code retrieval, which is what this
    package needs it for.
    """

    def __init__(self, api_key: str | None, model: str = "voyage-code-3") -> None:
        if not api_key:
            raise EmbeddingProviderError(
                "VOYAGE_API_KEY is not configured — set it to use codebase indexing/search"
            )
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self.dimensions = _VOYAGE_MODEL_DIMENSIONS.get(model, 1024)

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        try:
            for i in range(0, len(texts), EMBED_BATCH_SIZE):
                batch = texts[i : i + EMBED_BATCH_SIZE]
                result = self._client.embed(batch, model=self._model, input_type=input_type)
                vectors.extend(result.embeddings)
        except Exception as exc:  # voyageai raises its own exception hierarchy; normalize it
            raise EmbeddingProviderError(f"Voyage embedding request failed: {exc}") from exc
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]
