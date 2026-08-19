from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import jobs, models
from .audit import record_audit
from .db import SessionLocal, init_db
from .middleware import RequestLogMiddleware
from .routers import ALL_ROUTERS
from .settings import settings
from .time_utils import utcnow


def _reconcile_interrupted_pentests() -> None:
    """Mark any Pentest left at status='running' from a previous process as
    failed. A clean crash inside the worker loop already sets 'failed' (see
    jobs.py), so a row still 'running' at startup can only mean the process
    itself was killed mid-scan (e.g. a reload or host restart) — nothing
    else was left to finish it, so it would otherwise stay stuck forever.
    """
    db = SessionLocal()
    try:
        orphaned = db.query(models.Pentest).filter(models.Pentest.status == "running").all()
        for pentest in orphaned:
            pentest.status = "failed"
            pentest.finished_at = utcnow()
            db.commit()
            record_audit(
                db,
                pentest.org_id,
                pentest.created_by,
                "pentest.interrupted",
                pentest.target_label,
                {"reason": "backend restarted mid-scan"},
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _reconcile_interrupted_pentests()
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
app.add_middleware(RequestLogMiddleware)

for router in ALL_ROUTERS:
    app.include_router(router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
