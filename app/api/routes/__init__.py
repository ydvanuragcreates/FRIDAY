from fastapi import APIRouter

from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.executions import router as executions_router
from app.api.routes.indexing import router as indexing_router
from app.api.routes.projects import router as projects_router
from app.api.routes.tasks import router as tasks_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(tasks_router)
router.include_router(indexing_router)
router.include_router(projects_router)
router.include_router(conversations_router)
router.include_router(executions_router)
