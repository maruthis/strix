from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, db_dep
from ..jobs import MOCK_FINDINGS
from ..providers import get_github_provider

router = APIRouter(prefix="/api/pr-reviews", tags=["pr-reviews"])

STATUS_TABS = ["all", "awaiting_merge", "needs_attention", "merged_with_open_findings", "passed"]


def _serialize(p: models.PRReview, db: Session) -> dict:
    repo = db.get(models.Repository, p.repository_id)
    return {
        "id": p.id,
        "repository_id": p.repository_id,
        "repository_full_name": repo.full_name if repo else "",
        "pr_number": p.pr_number,
        "title": p.title,
        "author": p.author,
        "status": p.status,
        "findings_count": p.findings_count,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


@router.get("")
def list_pr_reviews(
    status_filter: str | None = None,
    repository_id: str | None = None,
    search: str | None = None,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> dict:
    q = db.query(models.PRReview).filter_by(org_id=org.id)
    if repository_id:
        q = q.filter(models.PRReview.repository_id == repository_id)
    if search:
        like = f"%{search}%"
        q = q.filter(models.PRReview.title.ilike(like))
    if status_filter and status_filter != "all":
        q = q.filter(models.PRReview.status == status_filter)
    reviews = q.order_by(models.PRReview.updated_at.desc()).all()

    all_reviews = db.query(models.PRReview).filter_by(org_id=org.id).all()
    counts = {tab: 0 for tab in STATUS_TABS}
    counts["all"] = len(all_reviews)
    for r in all_reviews:
        counts[r.status] = counts.get(r.status, 0) + 1

    return {"items": [_serialize(r, db) for r in reviews], "counts": counts}


class NewPRReviewIn(BaseModel):
    repository_id: str
    pr_number: int
    title: str
    author: str = "unknown"


@router.post("")
def trigger_pr_review(
    body: NewPRReviewIn,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> dict:
    repo = db.get(models.Repository, body.repository_id)
    if not repo or repo.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="repository_not_found")

    settings_row = _get_or_create_settings(db, org.id)

    review = models.PRReview(
        org_id=org.id,
        repository_id=repo.id,
        pr_number=body.pr_number,
        title=body.title,
        author=body.author,
    )
    db.add(review)
    db.flush()

    findings = random.sample(MOCK_FINDINGS, k=random.randint(0, 3))
    for f in findings:
        db.add(
            models.Issue(
                org_id=org.id,
                pr_review_id=review.id,
                repository_id=repo.id,
                title=f["title"],
                description=f["description"],
                severity=f["severity"],
                cvss=f["cvss"],
                technical_analysis=f["technical_analysis"],
                remediation_steps=f["remediation_steps"],
                poc_description=f["poc_description"],
                target=repo.full_name,
                endpoint=f["endpoint"],
                fix_effort=f["fix_effort"],
            )
        )
    review.findings_count = len(findings)

    blocking = any(f["severity"] in settings_row.blocking_severities for f in findings)
    if not findings:
        review.status = "passed"
    elif settings_row.block_prs_on_findings and blocking:
        review.status = "needs_attention"
    else:
        review.status = "awaiting_merge"
    db.commit()

    provider = get_github_provider()
    conclusion = "failure" if review.status == "needs_attention" else "success"
    provider.create_check_run(full_name=repo.full_name, pr_number=review.pr_number, conclusion=conclusion, summary=f"{review.findings_count} finding(s)")

    return _serialize(review, db)


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


def _get_or_create_settings(db: Session, org_id: str) -> models.PRReviewSettings:
    settings_row = db.get(models.PRReviewSettings, org_id)
    if not settings_row:
        settings_row = models.PRReviewSettings(org_id=org_id)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
    return settings_row


def _serialize_settings(s: models.PRReviewSettings) -> dict:
    return {
        "rereview_on_push": s.rereview_on_push,
        "target_branches": s.target_branches,
        "approve_clean_prs": s.approve_clean_prs,
        "block_prs_on_findings": s.block_prs_on_findings,
        "blocking_severities": s.blocking_severities,
        "exclude_bot_accounts": s.exclude_bot_accounts,
        "excluded_usernames": s.excluded_usernames,
        "allow_overage_reviews": s.allow_overage_reviews,
        "review_cap_per_dev": s.review_cap_per_dev,
        "review_cap_period": s.review_cap_period,
    }


@router.get("/settings")
def get_settings(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    return _serialize_settings(_get_or_create_settings(db, org.id))


class UpdateSettingsIn(BaseModel):
    rereview_on_push: bool | None = None
    target_branches: list[str] | None = None
    approve_clean_prs: bool | None = None
    block_prs_on_findings: bool | None = None
    blocking_severities: list[str] | None = None
    exclude_bot_accounts: bool | None = None
    excluded_usernames: list[str] | None = None
    allow_overage_reviews: bool | None = None
    review_cap_per_dev: int | None = None
    review_cap_period: str | None = None


@router.patch("/settings")
def update_settings(
    body: UpdateSettingsIn,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> dict:
    settings_row = _get_or_create_settings(db, org.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)
    db.commit()
    return _serialize_settings(settings_row)


# --------------------------------------------------------------------------
# GitHub webhook (PR events, @strix mentions)
# --------------------------------------------------------------------------

webhook_router = APIRouter(prefix="/api/webhooks", tags=["pr-reviews"])


@webhook_router.post("/github")
async def github_webhook(request: Request) -> dict:
    payload = await request.body()
    provider = get_github_provider()
    signature = request.headers.get("X-Hub-Signature-256")
    if not provider.verify_webhook_signature(payload=payload, signature_header=signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")
    # Real handling would parse `X-GitHub-Event` (pull_request / issue_comment),
    # match "@strix" mentions per TASKS.md P4-5, and call trigger_pr_review's
    # logic. Scaffold accepts and acknowledges so webhook delivery can be
    # configured and tested end-to-end against this endpoint.
    return {"ok": True}
