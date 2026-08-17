from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, current_user, db_dep
from .orgs import _record_audit
from .pentests import create_and_enqueue_pentest

router = APIRouter(prefix="/api/domains", tags=["domains"])


def _serialize(d: models.Domain) -> dict:
    return {
        "id": d.id,
        "hostname": d.hostname,
        "verified": d.verified,
        "verification_method": d.verification_method,
        "verification_token": d.verification_token,
        "last_tested_at": d.last_tested_at.isoformat() if d.last_tested_at else None,
    }


@router.get("")
def list_domains(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    domains = db.query(models.Domain).filter_by(org_id=org.id).order_by(models.Domain.created_at.desc()).all()
    return [_serialize(d) for d in domains]


@router.get("/{domain_id}")
def get_domain(domain_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    domain = db.get(models.Domain, domain_id)
    if not domain or domain.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    return _serialize(domain)


class AddDomainIn(BaseModel):
    hostname: str
    verification_method: str = "dns_txt"


@router.post("")
def add_domain(
    body: AddDomainIn,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> dict:
    existing = db.query(models.Domain).filter_by(org_id=org.id, hostname=body.hostname).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_added")
    domain = models.Domain(org_id=org.id, hostname=body.hostname, verification_method=body.verification_method)
    db.add(domain)
    db.commit()
    _record_audit(db, org.id, user.id, "domain.added", domain.hostname)
    return _serialize(domain)


@router.post("/{domain_id}/verify")
def verify_domain(domain_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    """Mock verification: in a real deployment this would resolve the DNS
    TXT record / fetch the well-known file and check it matches
    `verification_token`. Here it just marks the domain verified so the
    rest of the flow (scanning a domain) is exercisable locally."""
    domain = db.get(models.Domain, domain_id)
    if not domain or domain.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    domain.verified = True
    db.commit()
    return _serialize(domain)


@router.delete("/{domain_id}")
def remove_domain(domain_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    domain = db.get(models.Domain, domain_id)
    if not domain or domain.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    db.delete(domain)
    db.commit()
    return {"ok": True}


@router.post("/{domain_id}/scan")
async def trigger_scan(
    domain_id: str,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> dict:
    domain = db.get(models.Domain, domain_id)
    if not domain or domain.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    if not domain.verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="domain_not_verified")
    pentest = await create_and_enqueue_pentest(db, org, user, "domain", domain_id)
    return {"pentest_id": pentest.id}
