from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import jobs
from .db import init_db
from .routers import ALL_ROUTERS
from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await jobs.start_worker()
    yield
    await jobs.stop_worker()


app = FastAPI(title="Strix SaaS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in ALL_ROUTERS:
    app.include_router(router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
