from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, db_dep

router = APIRouter(prefix="/api/settings/webhooks", tags=["settings"])


def _serialize(w: models.Webhook) -> dict:
    return {
        "id": w.id,
        "url": w.url,
        "events": w.events,
        "secret": w.secret,
        "status": w.status,
        "created_at": w.created_at.isoformat(),
    }


@router.get("")
def list_webhooks(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    webhooks = db.query(models.Webhook).filter_by(org_id=org.id).all()
    return [_serialize(w) for w in webhooks]


class NewWebhookIn(BaseModel):
    url: str
    events: list[str] = ["pentest.completed", "issue.created", "pr_review.completed"]


@router.post("")
def create_webhook(body: NewWebhookIn, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    webhook = models.Webhook(org_id=org.id, url=body.url, events=body.events)
    db.add(webhook)
    db.commit()
    return _serialize(webhook)


@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    webhook = db.get(models.Webhook, webhook_id)
    if not webhook or webhook.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    db.delete(webhook)
    db.commit()
    return {"ok": True}
