"""Exercises the real HTTP request-building/response-parsing logic in
app/providers/git_hosting.py against an httpx.MockTransport instead of the
real network — this is what actually proves the GitHub/GitLab API calls
are built correctly (headers, URLs, self-hosted base_url handling, error
mapping), which router-level tests that monkeypatch these functions
outright can't cover."""

import httpx
import pytest

from app.providers import git_hosting


def _client_with(handler):
    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    return factory


def test_verify_github_returns_login_on_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.github.com/user"
        assert request.headers["authorization"] == "Bearer ghp_test"
        assert request.headers["accept"] == "application/vnd.github+json"
        return httpx.Response(200, json={"login": "octocat"})

    monkeypatch.setattr(git_hosting, "_client", _client_with(handler))
    assert git_hosting.verify_github(token="ghp_test", base_url=None) == "octocat"


def test_verify_github_uses_enterprise_api_v3_base_when_base_url_given(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://github.acme.internal/api/v3/user"
        return httpx.Response(200, json={"login": "acme-user"})

    monkeypatch.setattr(git_hosting, "_client", _client_with(handler))
    result = git_hosting.verify_github(token="t", base_url="https://github.acme.internal")
    assert result == "acme-user"


def test_verify_github_raises_on_401(monkeypatch):
    monkeypatch.setattr(git_hosting, "_client", _client_with(lambda r: httpx.Response(401, json={})))
    with pytest.raises(git_hosting.CredentialError) as exc_info:
        git_hosting.verify_github(token="bad", base_url=None)
    assert exc_info.value.code == "invalid_credentials"


def test_verify_github_raises_on_403(monkeypatch):
    monkeypatch.setattr(git_hosting, "_client", _client_with(lambda r: httpx.Response(403, json={})))
    with pytest.raises(git_hosting.CredentialError) as exc_info:
        git_hosting.verify_github(token="bad", base_url=None)
    assert exc_info.value.code == "invalid_credentials"


def test_verify_github_raises_provider_error_on_5xx(monkeypatch):
    monkeypatch.setattr(git_hosting, "_client", _client_with(lambda r: httpx.Response(500, json={})))
    with pytest.raises(git_hosting.CredentialError) as exc_info:
        git_hosting.verify_github(token="t", base_url=None)
    assert exc_info.value.code == "provider_error"


def test_verify_github_raises_provider_unreachable_on_network_error(monkeypatch):
    def factory() -> httpx.Client:
        def handler(request: httpx.Request):
            raise httpx.ConnectError("no route to host", request=request)

        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(git_hosting, "_client", factory)
    with pytest.raises(git_hosting.CredentialError) as exc_info:
        git_hosting.verify_github(token="t", base_url=None)
    assert exc_info.value.code == "provider_unreachable"


def test_list_repos_github_maps_fields(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "affiliation=owner" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {"full_name": "octocat/pub", "default_branch": "main", "private": False},
                {"full_name": "octocat/priv", "default_branch": "trunk", "private": True},
                {"full_name": "octocat/no-default-branch"},
            ],
        )

    monkeypatch.setattr(git_hosting, "_client", _client_with(handler))
    repos = git_hosting.list_repos_github(token="t", base_url=None)
    assert repos == [
        {"full_name": "octocat/pub", "default_branch": "main", "private": False},
        {"full_name": "octocat/priv", "default_branch": "trunk", "private": True},
        {"full_name": "octocat/no-default-branch", "default_branch": "main", "private": False},
    ]


def test_verify_gitlab_uses_private_token_header_and_username_field(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://gitlab.com/api/v4/user"
        assert request.headers["private-token"] == "glpat-test"
        return httpx.Response(200, json={"username": "acme-user"})

    monkeypatch.setattr(git_hosting, "_client", _client_with(handler))
    assert git_hosting.verify_gitlab(token="glpat-test", base_url=None) == "acme-user"


def test_verify_gitlab_self_hosted_base_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://gitlab.acme.internal/api/v4/user"
        return httpx.Response(200, json={"username": "acme-user"})

    monkeypatch.setattr(git_hosting, "_client", _client_with(handler))
    git_hosting.verify_gitlab(token="t", base_url="https://gitlab.acme.internal/")


def test_list_repos_gitlab_maps_fields(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "membership=true" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {"path_with_namespace": "acme/widgets", "default_branch": "main", "visibility": "private"},
                {"path_with_namespace": "acme/public-thing", "default_branch": "main", "visibility": "public"},
                {"path_with_namespace": "acme/no-branch", "visibility": "internal"},
            ],
        )

    monkeypatch.setattr(git_hosting, "_client", _client_with(handler))
    repos = git_hosting.list_repos_gitlab(token="t", base_url=None)
    assert repos == [
        {"full_name": "acme/widgets", "default_branch": "main", "private": True},
        {"full_name": "acme/public-thing", "default_branch": "main", "private": False},
        {"full_name": "acme/no-branch", "default_branch": "main", "private": True},
    ]


def test_list_repos_gitlab_raises_invalid_credentials_on_401(monkeypatch):
    monkeypatch.setattr(git_hosting, "_client", _client_with(lambda r: httpx.Response(401, json={})))
    with pytest.raises(git_hosting.CredentialError) as exc_info:
        git_hosting.list_repos_gitlab(token="bad", base_url=None)
    assert exc_info.value.code == "invalid_credentials"
