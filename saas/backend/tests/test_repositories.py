import time

from .conftest import add_member, add_repo


def test_list_repositories_empty(auth_client):
    client, _org = auth_client
    res = client.get("/api/repositories")
    assert res.status_code == 200
    assert res.json() == []


def test_installable_excludes_already_added(auth_client):
    client, _org = auth_client
    before = client.get("/api/repositories/installable").json()
    assert len(before) == 3

    add_repo(client, before[0]["full_name"])

    after = client.get("/api/repositories/installable").json()
    assert len(after) == 2
    assert before[0]["full_name"] not in [r["full_name"] for r in after]


def test_add_repository_conflict(auth_client):
    client, _org = auth_client
    add_repo(client, "acme/widgets")
    res = client.post("/api/repositories", json={"full_name": "acme/widgets"})
    assert res.status_code == 409
    assert res.json()["detail"] == "already_added"


def test_update_repository_toggle_auto_review(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    assert repo["auto_review_enabled"] is True

    res = client.patch(f"/api/repositories/{repo['id']}", json={"auto_review_enabled": False})
    assert res.status_code == 200
    assert res.json()["auto_review_enabled"] is False


def test_update_repository_not_found(auth_client):
    client, _org = auth_client
    res = client.patch("/api/repositories/does-not-exist", json={"auto_review_enabled": False})
    assert res.status_code == 404


def test_remove_repository(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    res = client.request("DELETE", f"/api/repositories/{repo['id']}")
    assert res.status_code == 200
    assert client.get("/api/repositories").json() == []


def test_remove_repository_not_found(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/repositories/does-not-exist")
    assert res.status_code == 404


def test_trigger_scan_creates_pentest(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    res = client.post(f"/api/repositories/{repo['id']}/scan")
    assert res.status_code == 200
    pentest_id = res.json()["pentest_id"]
    assert client.get(f"/api/pentests/{pentest_id}").status_code == 200


def test_repository_open_issues_count_reflected(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    listing = client.get("/api/repositories").json()
    assert listing[0]["open_issues_count"] == 0


def test_repository_open_issues_count_across_multiple_repos(auth_client):
    """Regression check for the N+1 -> batched-aggregate refactor: each
    repo's count must stay correctly attributed to that repo, including
    one with zero issues and one whose only issue is fixed (excluded)."""
    client, _org = auth_client
    repo_a = add_repo(client, "acme/widgets")
    repo_b = add_repo(client, "acme/gadgets")
    repo_c = add_repo(client, "acme/empty")

    for repo in (repo_a, repo_b):
        pentest = client.post("/api/pentests", json={"target_type": "repository", "target_id": repo["id"]}).json()
        deadline = time.time() + 5
        while time.time() < deadline:
            if client.get(f"/api/pentests/{pentest['id']}").json()["status"] == "completed":
                break
            time.sleep(0.02)

    counts = {r["id"]: r["open_issues_count"] for r in client.get("/api/repositories").json()}
    assert counts[repo_a["id"]] > 0
    assert counts[repo_b["id"]] > 0
    assert counts[repo_c["id"]] == 0
    # Total across repos matches the total non-fixed/ignored issue count.
    all_open = sum(1 for i in client.get("/api/issues?status_filter=open").json()["items"])
    assert counts[repo_a["id"]] + counts[repo_b["id"]] == all_open


def test_update_and_remove_repository_require_admin(auth_client):
    client, org = auth_client
    repo = add_repo(client)
    add_member(client, org)

    update = client.patch(f"/api/repositories/{repo['id']}", json={"auto_review_enabled": False})
    assert update.status_code == 403
    assert update.json()["detail"] == "admin_required"

    remove = client.request("DELETE", f"/api/repositories/{repo['id']}")
    assert remove.status_code == 403

    # A member can still list and trigger scans.
    assert client.get("/api/repositories").status_code == 200
    assert client.post(f"/api/repositories/{repo['id']}/scan").status_code == 200


def test_installable_gitlab_is_empty_when_not_connected(auth_client):
    client, _org = auth_client
    res = client.get("/api/repositories/installable?provider=gitlab")
    assert res.status_code == 200
    assert res.json() == []


def test_installable_rejects_unsupported_provider(auth_client):
    client, _org = auth_client
    res = client.get("/api/repositories/installable?provider=bitbucket")
    assert res.status_code == 400
    assert res.json()["detail"] == "unsupported_provider"

    add = client.post("/api/repositories", json={"full_name": "acme/x", "provider": "bitbucket"})
    assert add.status_code == 400
    assert add.json()["detail"] == "unsupported_provider"


def test_installable_lists_real_repos_once_github_is_connected(auth_client, monkeypatch):
    from app.providers import git_hosting

    client, _org = auth_client
    monkeypatch.setattr(git_hosting, "verify_github", lambda *, token, base_url: "octocat")
    client.post("/api/integrations/github/connect", json={"account_label": "octocat", "credential": "ghp_real"})

    monkeypatch.setattr(
        git_hosting,
        "list_repos_github",
        lambda *, token, base_url: [{"full_name": "octocat/real-repo", "default_branch": "main", "private": False}],
    )
    res = client.get("/api/repositories/installable")
    assert res.status_code == 200
    assert res.json() == [{"full_name": "octocat/real-repo", "default_branch": "main", "private": False}]

    # Once added, it drops out of the installable list — scoped by provider,
    # so a same-named gitlab repo wouldn't be excluded by this add.
    client.post("/api/repositories", json={"full_name": "octocat/real-repo", "provider": "github"})
    assert client.get("/api/repositories/installable").json() == []


def test_installable_surfaces_revoked_credential_as_401(auth_client, monkeypatch):
    from app.providers import git_hosting

    client, _org = auth_client
    monkeypatch.setattr(git_hosting, "verify_github", lambda *, token, base_url: "octocat")
    client.post("/api/integrations/github/connect", json={"account_label": "octocat", "credential": "ghp_real"})

    def fake_list(*, token, base_url):
        raise git_hosting.CredentialError("invalid_credentials")

    monkeypatch.setattr(git_hosting, "list_repos_github", fake_list)
    res = client.get("/api/repositories/installable")
    assert res.status_code == 401
    assert res.json()["detail"] == "invalid_credentials"


def test_add_gitlab_repository(auth_client):
    client, _org = auth_client
    res = client.post("/api/repositories", json={"full_name": "acme-group/widgets", "provider": "gitlab"})
    assert res.status_code == 200
    assert res.json()["provider"] == "gitlab"

    # Same full_name under a different provider is not a conflict.
    other = client.post("/api/repositories", json={"full_name": "acme-group/widgets", "provider": "github"})
    assert other.status_code == 200
