from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app


def test_reconciles_pentests_orphaned_by_a_previous_process_on_startup():
    # A Pentest left at status="running" when the app starts can only mean
    # the previous process was killed mid-scan (a clean in-process failure
    # already sets "failed" — see jobs.py). Seed one directly, bypassing the
    # API entirely, so it exists *before* the lifespan below runs.
    db = SessionLocal()
    try:
        org = models.Organization(name="Acme")
        db.add(org)
        db.flush()
        user = models.User(email="orphan-owner@example.com", name="Owner")
        db.add(user)
        db.flush()
        pentest = models.Pentest(
            org_id=org.id,
            target_type="repository",
            target_id="r1",
            target_label="acme/widgets",
            scan_mode="deep",
            status="running",
            created_by=user.id,
        )
        db.add(pentest)
        db.commit()
        pentest_id, org_id = pentest.id, org.id
    finally:
        db.close()

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    db = SessionLocal()
    try:
        refreshed = db.get(models.Pentest, pentest_id)
        assert refreshed.status == "failed"
        assert refreshed.finished_at is not None

        entry = (
            db.query(models.AuditLogEntry)
            .filter_by(org_id=org_id, action="pentest.interrupted")
            .first()
        )
        assert entry is not None
        assert entry.extra["reason"] == "backend restarted mid-scan"
    finally:
        db.close()


def test_startup_is_a_noop_when_nothing_is_orphaned():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
