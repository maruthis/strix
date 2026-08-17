from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, current_user, db_dep, require_admin
from ..providers import get_github_provider
from .orgs import _record_audit
from .pentests import create_and_enqueue_pentest

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


def _serialize(r: models.Repository, db: Session, open_issues_count: int | None = None) -> dict:
    if open_issues_count is None:
        open_issues_count = (
            db.query(models.Issue)
            .filter(models.Issue.repository_id == r.id, models.Issue.status.notin_(["fixed", "ignored"]))
            .count()
        )
    return {
        "id": r.id,
        "provider": r.provider,
        "full_name": r.full_name,
        "default_branch": r.default_branch,
        "auto_review_enabled": r.auto_review_enabled,
        "last_tested_at": r.last_tested_at.isoformat() if r.last_tested_at else None,
        "open_issues_count": open_issues_count,
    }


@router.get("")
def list_repositories(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    repos = db.query(models.Repository).filter_by(org_id=org.id).order_by(models.Repository.created_at.desc()).all()
    # One aggregate query for every repo's open-issue count instead of one
    # COUNT(*) per row (was N+1 — see saas/TASKS.md).
    counts = dict(
        db.query(models.Issue.repository_id, func.count(models.Issue.id))
        .filter(
            models.Issue.org_id == org.id,
            models.Issue.repository_id.isnot(None),
            models.Issue.status.notin_(["fixed", "ignored"]),
        )
        .group_by(models.Issue.repository_id)
        .all()
    )
    return [_serialize(r, db, counts.get(r.id, 0)) for r in repos]


@router.get("/installable")
def list_installable(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    provider = get_github_provider()
    already_added = {r.full_name for r in db.query(models.Repository).filter_by(org_id=org.id).all()}
    try:
        catalog = provider.installable_repositories()
    except NotImplementedError as exc:
        # RealGitHubProvider's methods are scaffolded but not implemented
        # yet (see providers/github.py) — surface a clear, actionable error
        # instead of an unhandled 500 once a real GitHub App is configured.
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="github_app_not_fully_configured",
        ) from exc
    return [repo for repo in catalog if repo["full_name"] not in already_added]


class AddRepositoryIn(BaseModel):
    full_name: str
    default_branch: str = "main"


@router.post("")
def add_repository(
    body: AddRepositoryIn,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> dict:
    existing = db.query(models.Repository).filter_by(org_id=org.id, full_name=body.full_name).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_added")
    repo = models.Repository(org_id=org.id, full_name=body.full_name, default_branch=body.default_branch)
    db.add(repo)
    db.commit()
    _record_audit(db, org.id, user.id, "repository.added", repo.full_name)
    return _serialize(repo, db)


class UpdateRepositoryIn(BaseModel):
    auto_review_enabled: bool


@router.patch("/{repository_id}")
def update_repository(
    repository_id: str,
    body: UpdateRepositoryIn,
    org: models.Organization = Depends(current_org),
    _admin=Depends(require_admin),
    db: Session = Depends(db_dep),
) -> dict:
    # Admin-only: auto-review is an org security-posture setting, like PR
    # review settings and LLM config.
    repo = db.get(models.Repository, repository_id)
    if not repo or repo.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    repo.auto_review_enabled = body.auto_review_enabled
    db.commit()
    return _serialize(repo, db)


@router.delete("/{repository_id}")
def remove_repository(
    repository_id: str,
    org: models.Organization = Depends(current_org),
    _admin=Depends(require_admin),
    db: Session = Depends(db_dep),
) -> dict:
    repo = db.get(models.Repository, repository_id)
    if not repo or repo.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    db.delete(repo)
    db.commit()
    return {"ok": True}


@router.post("/{repository_id}/scan")
async def trigger_scan(
    repository_id: str,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> dict:
    pentest = await create_and_enqueue_pentest(db, org, user, "repository", repository_id)
    return {"pentest_id": pentest.id}
