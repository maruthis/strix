from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, require_admin, db_dep
from ..providers import get_billing_provider

router = APIRouter(prefix="/api/settings/billing", tags=["settings"])


def _serialize(sub: models.Subscription) -> dict:
    return {
        "plan": sub.plan,
        "status": sub.status,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "card_added": sub.card_added,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


def _get_or_create_subscription(db: Session, org_id: str) -> models.Subscription:
    sub = db.get(models.Subscription, org_id)
    if not sub:
        sub = models.Subscription(org_id=org_id)
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


@router.get("")
def get_billing(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    sub = _get_or_create_subscription(db, org.id)
    return _serialize(sub)


@router.post("/add-card")
def add_card(org: models.Organization = Depends(current_org), _admin=Depends(require_admin), db: Session = Depends(db_dep)) -> dict:
    provider = get_billing_provider()
    provider.attach_card(org_id=org.id)
    sub = _get_or_create_subscription(db, org.id)
    sub.card_added = True
    sub.status = "active"
    db.commit()
    return _serialize(sub)


@router.get("/invoices")
def list_invoices(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    provider = get_billing_provider()
    return provider.list_invoices(org_id=org.id)
