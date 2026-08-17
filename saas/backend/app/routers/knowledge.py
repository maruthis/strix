from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, db_dep

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _serialize(k: models.KnowledgeEntry) -> dict:
    return {
        "id": k.id,
        "type": k.type,
        "description": k.description,
        "scope_type": k.scope_type,
        "scope_id": k.scope_id,
        "created_at": k.created_at.isoformat(),
    }


@router.get("")
def list_knowledge(
    search: str | None = None,
    scope_type: str | None = None,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> list[dict]:
    q = db.query(models.KnowledgeEntry).filter_by(org_id=org.id)
    if scope_type and scope_type != "all":
        q = q.filter(models.KnowledgeEntry.scope_type == scope_type)
    if search:
        q = q.filter(models.KnowledgeEntry.description.ilike(f"%{search}%"))
    entries = q.order_by(models.KnowledgeEntry.created_at.desc()).all()
    return [_serialize(e) for e in entries]


class NewKnowledgeIn(BaseModel):
    type: str = "business_logic"
    description: str
    scope_type: str = "global"
    scope_id: str | None = None


@router.post("")
def add_knowledge(
    body: NewKnowledgeIn,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> dict:
    if not body.description.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="description_required")
    entry = models.KnowledgeEntry(
        org_id=org.id,
        type=body.type,
        description=body.description.strip(),
        scope_type=body.scope_type,
        scope_id=body.scope_id,
    )
    db.add(entry)
    db.commit()
    return _serialize(entry)


@router.delete("/{entry_id}")
def delete_knowledge(entry_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    entry = db.get(models.KnowledgeEntry, entry_id)
    if not entry or entry.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    db.delete(entry)
    db.commit()
    return {"ok": True}


def relevant_entries(db: Session, org_id: str, *, repository_id: str | None = None, domain_id: str | None = None) -> list[models.KnowledgeEntry]:
    """Knowledge entries that should be injected into agent context for a
    given scan/chat target: global entries plus ones scoped to this exact
    repository/domain. Used by jobs.py and the chat router (TASKS.md P8-4)."""
    q = db.query(models.KnowledgeEntry).filter_by(org_id=org_id)
    entries = q.all()
    return [
        e
        for e in entries
        if e.scope_type == "global"
        or (e.scope_type == "repository" and e.scope_id == repository_id)
        or (e.scope_type == "domain" and e.scope_id == domain_id)
    ]
