from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, current_user, db_dep
from .orgs import _record_audit

router = APIRouter(prefix="/api/issues", tags=["issues"])

VALID_STATUSES = {"open", "in_progress", "snoozed", "fixed", "ignored"}


def _serialize(i: models.Issue) -> dict:
    return {
        "id": i.id,
        "org_id": i.org_id,
        "pentest_id": i.pentest_id,
        "pr_review_id": i.pr_review_id,
        "repository_id": i.repository_id,
        "domain_id": i.domain_id,
        "title": i.title,
        "description": i.description,
        "severity": i.severity,
        "status": i.status,
        "cvss": i.cvss,
        "cvss_breakdown": i.cvss_breakdown,
        "technical_analysis": i.technical_analysis,
        "remediation_steps": i.remediation_steps,
        "poc_description": i.poc_description,
        "poc_script_code": i.poc_script_code,
        "code_before": i.code_before,
        "code_after": i.code_after,
        "target": i.target,
        "endpoint": i.endpoint,
        "fix_effort": i.fix_effort,
        "created_at": i.created_at.isoformat(),
        "updated_at": i.updated_at.isoformat(),
    }


@router.get("")
def list_issues(
    status_filter: str | None = None,
    severity: str | None = None,
    repository_id: str | None = None,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> dict:
    q = db.query(models.Issue).filter_by(org_id=org.id)
    if status_filter:
        q = q.filter(models.Issue.status == status_filter)
    if severity:
        q = q.filter(models.Issue.severity == severity)
    if repository_id:
        q = q.filter(models.Issue.repository_id == repository_id)
    issues = q.order_by(models.Issue.created_at.desc()).all()

    all_open = db.query(models.Issue).filter_by(org_id=org.id).filter(models.Issue.status != "fixed", models.Issue.status != "ignored").all()
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in all_open:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

    status_counts = {s: 0 for s in ["all", "open", "in_progress", "snoozed", "fixed", "ignored"]}
    all_issues = db.query(models.Issue).filter_by(org_id=org.id).all()
    status_counts["all"] = len(all_issues)
    for issue in all_issues:
        status_counts[issue.status] = status_counts.get(issue.status, 0) + 1

    return {
        "items": [_serialize(i) for i in issues],
        "severity_counts": severity_counts,
        "status_counts": status_counts,
    }


@router.get("/{issue_id}")
def get_issue(issue_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> dict:
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    return _serialize(issue)


class UpdateIssueStatusIn(BaseModel):
    status: str


@router.patch("/{issue_id}/status")
def update_issue_status(
    issue_id: str,
    body: UpdateIssueStatusIn,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> dict:
    if body.status not in VALID_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_status")
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    issue.status = body.status
    db.commit()
    _record_audit(db, org.id, user.id, "issue.status_updated", issue.title, {"status": body.status})
    return _serialize(issue)
