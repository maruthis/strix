from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, db_dep

router = APIRouter(prefix="/api/settings/audit-logs", tags=["settings"])


@router.get("")
def list_audit_logs(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    entries = (
        db.query(models.AuditLogEntry)
        .filter_by(org_id=org.id)
        .order_by(models.AuditLogEntry.created_at.desc())
        .limit(200)
        .all()
    )
    out = []
    for e in entries:
        actor = db.get(models.User, e.actor_user_id) if e.actor_user_id else None
        out.append(
            {
                "id": e.id,
                "actor_email": actor.email if actor else "system",
                "action": e.action,
                "target": e.target,
                "extra": e.extra,
                "created_at": e.created_at.isoformat(),
            }
        )
    return out
