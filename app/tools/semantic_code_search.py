from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.indexing.embeddings import EmbeddingProviderError
from app.indexing.factory import get_retriever
from app.indexing.retriever import ProjectNotIndexedError

MAX_RESULTS = 10


class SemanticCodeSearchInput(BaseModel):
    query: str = Field(
        description=(
            "A natural-language description of the code you're looking for, e.g. "
            "'where retries are capped' or 'how the workspace path traversal check "
            "works' — not necessarily an exact string that appears in the code."
        )
    )
    top_k: int = Field(default=5, ge=1, le=MAX_RESULTS, description="How many results to return.")


@tool("semantic_code_search", args_schema=SemanticCodeSearchInput)
def semantic_code_search(query: str, top_k: int = 5) -> str:
    """Search the indexed codebase by meaning rather than exact text —
    finds conceptually related functions/classes even if they don't
    contain your exact wording. Requires the project to have been
    indexed first via POST /api/projects/{project_id}/index. Use this
    when you have a concept or question in mind but don't know the exact
    file, function, or string to look for; once you have a candidate
    file path, use read_file to see its full, current, authoritative
    content — search results are chunked excerpts, not the whole file.
    """
    project_id = get_settings().default_project_id
    try:
        results = get_retriever().search(project_id, query, top_k=top_k)
    except ProjectNotIndexedError as exc:
        return f"Error: {exc}"
    except EmbeddingProviderError as exc:
        return f"Error: {exc}"

    if not results:
        return f"No semantically matching code found for '{query}'"

    rendered = []
    for r in results:
        location = f"{r.file_path}:{r.start_line}-{r.end_line}"
        label = f"{r.symbol_type} {r.symbol}" if r.symbol else "module-level code"
        rendered.append(
            f"{location} [{r.language}, {label}, score={r.score:.3f}]\n{r.content}"
        )
    return "\n\n---\n\n".join(rendered)
