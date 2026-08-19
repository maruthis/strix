from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..audit import record_audit as _record_audit
from ..deps import current_org, current_user, db_dep

router = APIRouter(prefix="/api/chat", tags=["chat"])

CATEGORIES = ["web", "code", "cloud", "recon", "network", "threat_intel", "compliance"]

SUGGESTIONS: dict[str, list[dict]] = {
    "web": [
        {"title": "Test API authorization", "prompt": "Check my API endpoints for broken access control and privilege escalation issues."},
        {"title": "Analyze OAuth flows", "prompt": "Evaluate the token handling and redirect validation in my OAuth setup."},
        {"title": "Detect SSRF vectors", "prompt": "Find server-side request forgery paths that could reach internal services."},
        {"title": "Audit business logic", "prompt": "Look for logic flaws in my app - race conditions, state manipulation, bypasses."},
    ],
    "code": [
        {"title": "Review authentication code", "prompt": "Review my authentication implementation for common vulnerabilities."},
        {"title": "Find injection flaws", "prompt": "Search the codebase for SQL/command/template injection sinks."},
        {"title": "Check secrets handling", "prompt": "Look for hardcoded secrets or unsafe secret storage in the codebase."},
        {"title": "Review dependency risk", "prompt": "Flag outdated or vulnerable dependencies in the project manifest."},
    ],
    "cloud": [
        {"title": "Audit IAM policies", "prompt": "Review IAM roles/policies for overly permissive access."},
        {"title": "Check storage exposure", "prompt": "Look for publicly exposed storage buckets or misconfigured ACLs."},
        {"title": "Review network exposure", "prompt": "Check security groups/firewalls for overly broad ingress rules."},
        {"title": "Audit secrets management", "prompt": "Review how cloud secrets/credentials are stored and rotated."},
    ],
    "recon": [
        {"title": "Map external attack surface", "prompt": "Enumerate subdomains, exposed services, and endpoints for my domain."},
        {"title": "Fingerprint tech stack", "prompt": "Identify frameworks, CMS, and versions in use across my assets."},
    ],
    "network": [
        {"title": "Scan open ports", "prompt": "Identify open ports and exposed services on my network target."},
        {"title": "Review segmentation", "prompt": "Assess network segmentation between environments."},
    ],
    "threat_intel": [
        {"title": "Check breach exposure", "prompt": "Check if my domain/org has appeared in known breach data."},
    ],
    "compliance": [
        {"title": "Map findings to SOC 2", "prompt": "Map current open findings to relevant SOC 2 control gaps."},
    ],
}


@router.get("/suggestions")
def get_suggestions() -> dict:
    return {"categories": CATEGORIES, "suggestions": SUGGESTIONS}


def _serialize_session(s: models.ChatSession) -> dict:
    return {"id": s.id, "title": s.title, "category": s.category, "created_at": s.created_at.isoformat()}


def _serialize_message(m: models.ChatMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}


@router.get("/sessions")
def list_sessions(
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> list[dict]:
    sessions = (
        db.query(models.ChatSession)
        .filter_by(org_id=org.id, user_id=user.id)
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )
    return [_serialize_session(s) for s in sessions]


class NewSessionIn(BaseModel):
    category: str = "web"


@router.post("/sessions")
def create_session(
    body: NewSessionIn,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> dict:
    session = models.ChatSession(org_id=org.id, user_id=user.id, category=body.category)
    db.add(session)
    db.commit()
    _record_audit(db, org.id, user.id, "chat.session_created", session.category)
    return _serialize_session(session)


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str, org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    session = db.get(models.ChatSession, session_id)
    if not session or session.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    return [_serialize_message(m) for m in session.messages]


class NewMessageIn(BaseModel):
    content: str
    repository_ids: list[str] = []


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: str,
    body: NewMessageIn,
    org: models.Organization = Depends(current_org),
    db: Session = Depends(db_dep),
) -> list[dict]:
    session = db.get(models.ChatSession, session_id)
    if not session or session.org_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    if not body.content.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="content_required")

    user_msg = models.ChatMessage(session_id=session.id, role="user", content=body.content.strip())
    db.add(user_msg)

    from .knowledge import relevant_entries

    context_entries = relevant_entries(db, org.id, repository_id=body.repository_ids[0] if body.repository_ids else None)
    reply = _mock_agent_reply(body.content, session.category, context_entries)
    assistant_msg = models.ChatMessage(session_id=session.id, role="assistant", content=reply)
    db.add(assistant_msg)

    if session.title == "New chat":
        session.title = body.content.strip()[:60]

    db.commit()
    return [_serialize_message(user_msg), _serialize_message(assistant_msg)]


def _mock_agent_reply(prompt: str, category: str, context_entries: list[models.KnowledgeEntry]) -> str:
    """Placeholder assistant reply. Real orchestration should stream this
    from the upstream strix agent engine (TASKS.md P9-4) — invoked the same
    way jobs.py invokes it for pentests, but conversationally. Left as a
    canned response here since that requires Docker/LLM credentials this
    scaffold doesn't assume are configured."""
    context_note = ""
    if context_entries:
        context_note = f" I'll factor in {len(context_entries)} piece(s) of knowledge base context you've added."
    return (
        f"Got it — I'll start a {category.replace('_', ' ')} review for: “{prompt}”.{context_note} "
        "This is a placeholder reply; connect a real scan/LLM backend "
        "(SAAS_ENABLE_REAL_SCAN=1) to get live agent output here."
    )
