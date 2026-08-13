from fastapi import APIRouter, Depends, HTTPException

from app.indexing.vector_store import InvalidProjectIdError
from app.models.schemas import IndexRequest, IndexResponse
from app.services.indexing_service import IndexingService, IndexingServiceError, get_indexing_service

router = APIRouter()


@router.post("/api/projects/{project_id}/index", response_model=IndexResponse)
def index_project(
    project_id: str,
    request: IndexRequest = IndexRequest(),
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> IndexResponse:
    """Run the indexing pipeline (file discovery -> parsing -> chunking ->
    metadata extraction -> embeddings -> Qdrant) over `request.path`
    (default: the whole workspace) and store it under `project_id`'s
    collection. `errors` lists any individual files that were skipped —
    those don't fail the request as a whole.

    `project_id` here is a Qdrant collection namespace slug (Phase 6),
    unrelated to the `projects` DB table's UUID primary key (Phase 7,
    see app/api/routes/projects.py) — they share a name and a path
    prefix but are two independent identifier spaces today. See README >
    "Project scope" for the reasoning and the (currently unbuilt) seam
    where a future phase could unify them.
    """
    try:
        result = indexing_service.index_project(project_id, request.path)
    except InvalidProjectIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IndexingServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return IndexResponse(
        project_id=result.project_id,
        collection_name=result.collection_name,
        files_indexed=result.files_indexed,
        chunks_indexed=result.chunks_indexed,
        errors=result.errors,
    )
