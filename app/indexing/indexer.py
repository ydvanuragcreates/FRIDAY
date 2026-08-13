"""Orchestrates the indexing pipeline:

    file discovery -> code parsing -> chunking -> metadata extraction
    -> embeddings -> Qdrant

Every stage it calls into (discovery, parsing, chunking, embeddings,
vector_store) is plain Python with no LangChain/LangGraph involvement —
this module is the pipeline, not an agent.
"""

from dataclasses import dataclass, field
from pathlib import Path

from app.core.workspace import WorkspacePathError, resolve_workspace_path
from app.indexing.chunking import CodeChunk, chunk_file
from app.indexing.discovery import discover_source_files, relative_posix_path
from app.indexing.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.indexing.languages import detect_language
from app.indexing.parsing import parse_code_units
from app.indexing.vector_store import VectorStore, collection_name_for_project


@dataclass
class IndexResult:
    project_id: str
    collection_name: str
    files_indexed: int
    chunks_indexed: int
    errors: list[str] = field(default_factory=list)


def _embedding_text(chunk: CodeChunk) -> str:
    """Text actually sent to the embedding model — a short header plus
    the code. The header gives the embedding model context (which file,
    which symbol) that raw code alone doesn't carry, which measurably
    helps retrieval for short or generically-named snippets. The stored
    `content` payload stays pure code so read-outs/diffs aren't polluted.
    """
    header = f"# File: {chunk.file_path}"
    if chunk.symbol:
        header += f"\n# {chunk.symbol_type or 'symbol'}: {chunk.symbol}"
    return f"{header}\n\n{chunk.content}"


class CodebaseIndexer:
    def __init__(self, vector_store: VectorStore, embedding_provider: EmbeddingProvider) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider

    def index_path(self, project_id: str, subpath: str = ".") -> IndexResult:
        collection_name = collection_name_for_project(project_id)

        try:
            root = resolve_workspace_path(subpath)
        except WorkspacePathError as exc:
            return IndexResult(project_id, collection_name, 0, 0, errors=[str(exc)])

        if not root.exists():
            return IndexResult(project_id, collection_name, 0, 0, errors=[f"'{subpath}' does not exist"])

        files = discover_source_files(root)
        chunks: list[CodeChunk] = []
        errors: list[str] = []

        for path in files:
            chunks.extend(self._chunk_one_file(path, errors))

        if not chunks:
            return IndexResult(project_id, collection_name, len(files), 0, errors=errors)

        try:
            embeddings = self._embedding_provider.embed_documents([_embedding_text(c) for c in chunks])
        except EmbeddingProviderError as exc:
            errors.append(str(exc))
            return IndexResult(project_id, collection_name, len(files), 0, errors=errors)

        self._vector_store.ensure_collection(collection_name, self._embedding_provider.dimensions)
        self._vector_store.upsert_chunks(collection_name, chunks, embeddings)

        return IndexResult(project_id, collection_name, len(files), len(chunks), errors=errors)

    def _chunk_one_file(self, path: Path, errors: list[str]) -> list[CodeChunk]:
        rel_path = relative_posix_path(path)
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"skipped '{rel_path}': {exc}")
            return []

        language = detect_language(rel_path)
        units = parse_code_units(language, text)
        return chunk_file(rel_path, language, text, units)
