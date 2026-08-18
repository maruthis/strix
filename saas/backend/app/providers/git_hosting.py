"""Real, per-org GitHub/GitLab connections authenticated with a
user-supplied Personal/Project Access Token (+ optional self-hosted base
URL) — this is what backs the "Connect" flow on Settings > Integrations
and the Repositories "Add Repository" picker.

This is deliberately separate from `providers/github.py`'s `RealGitHubProvider`,
which scaffolds a *different*, still-unimplemented model (a GitHub App
registered once for the whole deployment, used for PR-review check-runs
and webhooks). Here, credentials are per-org and per-token, which is the
right fit for a multi-tenant product and needs no app registration at
all — the tradeoff is the caller manages their own token instead of an
OAuth consent screen. Posting check-runs/PR comments and webhooks are out
of scope for this path for now; see saas/TASKS.md.
"""

from __future__ import annotations

from typing import Any

import httpx

GITHUB_DEFAULT_API_BASE = "https://api.github.com"
GITLAB_DEFAULT_API_BASE = "https://gitlab.com/api/v4"

_TIMEOUT = 10.0


class CredentialError(Exception):
    """Raised when a token/URL/username combination can't authenticate,
    or the provider can't be reached at all. `code` is a stable machine
    detail string for the API response."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _client() -> httpx.Client:
    # A thin seam so tests can inject an httpx.MockTransport instead of
    # making real network calls, while production code takes the default
    # real-network client.
    return httpx.Client(timeout=_TIMEOUT)


def _get_json(url: str, headers: dict[str, str]) -> Any:
    try:
        with _client() as client:
            res = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise CredentialError("provider_unreachable") from exc
    if res.status_code in (401, 403):
        raise CredentialError("invalid_credentials")
    if res.status_code >= 400:
        raise CredentialError("provider_error")
    return res.json()


def _github_api_base(base_url: str | None) -> str:
    return f"{base_url.rstrip('/')}/api/v3" if base_url else GITHUB_DEFAULT_API_BASE


def _github_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def verify_github(*, token: str, base_url: str | None) -> str:
    """Confirms the token authenticates, and returns the GitHub login it belongs to."""
    data = _get_json(f"{_github_api_base(base_url)}/user", _github_headers(token))
    return data["login"]


def list_repos_github(*, token: str, base_url: str | None) -> list[dict[str, Any]]:
    url = f"{_github_api_base(base_url)}/user/repos?per_page=100&affiliation=owner,collaborator,organization_member"
    data = _get_json(url, _github_headers(token))
    return [
        {"full_name": r["full_name"], "default_branch": r.get("default_branch") or "main", "private": bool(r.get("private"))}
        for r in data
    ]


def _gitlab_api_base(base_url: str | None) -> str:
    return f"{base_url.rstrip('/')}/api/v4" if base_url else GITLAB_DEFAULT_API_BASE


def _gitlab_headers(token: str) -> dict[str, str]:
    return {"PRIVATE-TOKEN": token}


def verify_gitlab(*, token: str, base_url: str | None) -> str:
    """Confirms the token authenticates, and returns the GitLab username it belongs to."""
    data = _get_json(f"{_gitlab_api_base(base_url)}/user", _gitlab_headers(token))
    return data["username"]


def list_repos_gitlab(*, token: str, base_url: str | None) -> list[dict[str, Any]]:
    url = f"{_gitlab_api_base(base_url)}/projects?membership=true&per_page=100"
    data = _get_json(url, _gitlab_headers(token))
    return [
        {
            "full_name": p["path_with_namespace"],
            "default_branch": p.get("default_branch") or "main",
            "private": p.get("visibility") != "public",
        }
        for p in data
    ]
