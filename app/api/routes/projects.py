import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectNotFoundError, ProjectService, get_project_service

router = APIRouter()


@router.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    project = await project_service.create_project(user_id, request)
    return ProjectResponse.model_validate(project)


@router.get("/api/projects", response_model=list[ProjectResponse])
async def list_projects(
    user_id: uuid.UUID = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    projects = await project_service.list_projects(user_id)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    try:
        project = await project_service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectResponse.model_validate(project)


@router.patch("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    request: ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    try:
        project = await project_service.update_project(project_id, request)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectResponse.model_validate(project)


@router.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    project_service: ProjectService = Depends(get_project_service),
) -> None:
    try:
        await project_service.delete_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
