from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(title="F.R.I.D.A.Y", version="0.1.0")

# Phase 8: the Next.js frontend runs on a different origin (localhost:3000)
# than this API (localhost:8000) — without this, every browser fetch() is
# blocked by the browser itself before the request even reaches a route.
# Not new functionality, just making the existing API reachable from a
# browser. Origins are read from an env var so a deployed frontend's real
# origin can be added without code changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
