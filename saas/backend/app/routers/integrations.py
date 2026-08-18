"""Third-party integrations (source control, chat, issue tracking).

Mirrors the "shown once secret"/mock-provider pattern used elsewhere in
this scaffold: connecting is a real DB write scoped to the org, driven by
account/credential info the caller actually types into the Connect modal,
but there's no live OAuth handshake or API call behind it — that requires
a registered app with each provider that only the operator of a deployment
can create (see CONFIG.md for the same tradeoff already made for the
GitHub App and Stripe integrations). If a credential is supplied we only
ever keep its last 4 characters (`credential_last4`), purely for display
("connected as ... using a token ending in 1234") — nothing here calls out
to the provider with it, so there's no reason to hold the full value.

`configure_url` in the catalog is a real, provider-owned settings page
(e.g. GitHub's "Installed GitHub Apps" list) that the frontend opens in a
new tab from the "Configure" action — not something this backend can
deep-link into a specific installation without a real App registration.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..deps import current_org, current_user, db_dep, require_admin
from .orgs import _record_audit

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

CATALOG = [
    {"provider": "github", "category": "code", "label": "GitHub", "configure_url": "https://github.com/settings/installations"},
    {"provider": "gitlab", "category": "code", "label": "GitLab", "configure_url": "https://gitlab.com/-/user_settings/applications"},
    {"provider": "bitbucket", "category": "code", "label": "Bitbucket"},
    {"provider": "slack", "category": "communication", "label": "Slack"},
    {"provider": "msteams", "category": "communication", "label": "Microsoft Teams", "coming_soon": True},
    {"provider": "jira", "category": "issue_tracking", "label": "Jira"},
    {"provider": "linear", "category": "issue_tracking", "label": "Linear"},
]
CATALOG_BY_PROVIDER = {c["provider"]: c for c in CATALOG}


def _serialize(entry: dict, integration: models.Integration | None) -> dict:
    return {
        "provider": entry["provider"],
        "category": entry["category"],
        "label": entry["label"],
        "coming_soon": entry.get("coming_soon", False),
        "configure_url": entry.get("configure_url"),
        "status": "connected" if integration else "not_connected",
        "account_label": integration.account_label if integration else None,
        "credential_last4": integration.credential_last4 if integration else None,
        "connected_at": integration.connected_at.isoformat() if integration else None,
    }


@router.get("")
def list_integrations(org: models.Organization = Depends(current_org), db: Session = Depends(db_dep)) -> list[dict]:
    rows = {i.provider: i for i in db.query(models.Integration).filter_by(org_id=org.id).all()}
    return [_serialize(entry, rows.get(entry["provider"])) for entry in CATALOG]


class ConnectIn(BaseModel):
    account_label: str
    credential: str | None = None


@router.post("/{provider}/connect")
def connect_integration(
    provider: str,
    body: ConnectIn,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
    _admin=Depends(require_admin),
) -> dict:
    entry = CATALOG_BY_PROVIDER.get(provider)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown_provider")
    if entry.get("coming_soon"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="provider_not_yet_available")

    account_label = body.account_label.strip()
    if not account_label:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="account_label_required")
    credential = (body.credential or "").strip()
    credential_last4 = credential[-4:] if credential else None

    integration = db.query(models.Integration).filter_by(org_id=org.id, provider=provider).first()
    if integration:
        integration.account_label = account_label
        integration.credential_last4 = credential_last4
    else:
        integration = models.Integration(org_id=org.id, provider=provider, account_label=account_label, credential_last4=credential_last4)
        db.add(integration)
    db.commit()
    db.refresh(integration)
    _record_audit(db, org.id, user.id, "integration.connected", entry["label"], {"account_label": account_label})
    return _serialize(entry, integration)


@router.delete("/{provider}")
def disconnect_integration(
    provider: str,
    org: models.Organization = Depends(current_org),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
    _admin=Depends(require_admin),
) -> dict:
    entry = CATALOG_BY_PROVIDER.get(provider)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown_provider")

    integration = db.query(models.Integration).filter_by(org_id=org.id, provider=provider).first()
    if integration:
        db.delete(integration)
        db.commit()
        _record_audit(db, org.id, user.id, "integration.disconnected", entry["label"])
    return _serialize(entry, None)
