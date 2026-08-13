from app.indexing.embeddings import EmbeddingProvider
from app.indexing.vector_store import VectorStore, RetrievedChunk, collection_name_for_project


class ProjectNotIndexedError(Exception):
    """Raised when a semantic search targets a project that has no
    collection yet — i.e. POST /api/projects/{project_id}/index hasn't
    been run (successfully) for it.
    """


class CodeRetriever:
    """Query-side counterpart to CodebaseIndexer: embed a query and search
    the matching project's collection. No LangChain/LangGraph imports —
    app/tools/semantic_code_search.py is the only caller that's aware an
    agent exists.
    """

    def __init__(self, vector_store: VectorStore, embedding_provider: EmbeddingProvider) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider

    def search(self, project_id: str, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        collection_name = collection_name_for_project(project_id)
        if not self._vector_store.collection_exists(collection_name):
            raise ProjectNotIndexedError(
                f"project '{project_id}' has not been indexed yet — "
                f"call POST /api/projects/{project_id}/index first"
            )

        query_vector = self._embedding_provider.embed_query(query)
        return self._vector_store.search(collection_name, query_vector, top_k=top_k)
