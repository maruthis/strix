from .conftest import add_repo


def test_settings_defaults_and_update(auth_client):
    client, _org = auth_client
    res = client.get("/api/pr-reviews/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["block_prs_on_findings"] is True
    assert body["blocking_severities"] == ["critical", "high"]

    update = client.patch(
        "/api/pr-reviews/settings",
        json={
            "rereview_on_push": True,
            "target_branches": ["main", "release/*"],
            "blocking_severities": ["critical"],
            "excluded_usernames": ["dependabot"],
            "review_cap_per_dev": 10,
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["rereview_on_push"] is True
    assert body["target_branches"] == ["main", "release/*"]
    assert body["blocking_severities"] == ["critical"]
    assert body["excluded_usernames"] == ["dependabot"]
    assert body["review_cap_per_dev"] == 10
    # Unset fields are unaffected by a partial update.
    assert body["allow_overage_reviews"] is True


def test_trigger_review_repository_not_found(auth_client):
    client, _org = auth_client
    res = client.post("/api/pr-reviews", json={"repository_id": "nope", "pr_number": 1, "title": "x"})
    assert res.status_code == 404


def test_trigger_review_and_list(auth_client):
    client, _org = auth_client
    repo = add_repo(client)

    res = client.post("/api/pr-reviews", json={"repository_id": repo["id"], "pr_number": 7, "title": "Add feature", "author": "octocat"})
    assert res.status_code == 200
    review = res.json()
    assert review["status"] in {"passed", "needs_attention", "awaiting_merge"}
    assert review["repository_full_name"] == repo["full_name"]

    listing = client.get("/api/pr-reviews").json()
    assert listing["counts"]["all"] == 1
    assert len(listing["items"]) == 1

    filtered = client.get(f"/api/pr-reviews?status_filter={review['status']}").json()
    assert len(filtered["items"]) == 1

    by_repo = client.get(f"/api/pr-reviews?repository_id={repo['id']}").json()
    assert len(by_repo["items"]) == 1

    by_search = client.get("/api/pr-reviews?search=Add feature").json()
    assert len(by_search["items"]) == 1

    by_search_miss = client.get("/api/pr-reviews?search=nonexistent-title").json()
    assert by_search_miss["items"] == []


def test_trigger_review_forces_needs_attention_with_low_blocking_severity(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    # Blocking on "low" makes any non-empty findings sample block the PR,
    # avoiding flakiness from the mock scanner's random severity mix.
    client.patch("/api/pr-reviews/settings", json={"blocking_severities": ["critical", "high", "medium", "low"]})

    seen_statuses = set()
    for i in range(10):
        review = client.post(
            "/api/pr-reviews", json={"repository_id": repo["id"], "pr_number": i, "title": f"PR {i}", "author": "octocat"}
        ).json()
        seen_statuses.add(review["status"])
    assert seen_statuses <= {"passed", "needs_attention"}


def test_trigger_review_awaiting_merge_when_findings_dont_block(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    # No severity is blocking, so any run with findings must land on
    # "awaiting_merge" rather than "needs_attention" (empty findings still
    # produce "passed", so loop until we see a non-empty result).
    client.patch("/api/pr-reviews/settings", json={"blocking_severities": []})

    seen_statuses = set()
    for i in range(15):
        review = client.post(
            "/api/pr-reviews", json={"repository_id": repo["id"], "pr_number": i, "title": f"PR {i}", "author": "octocat"}
        ).json()
        seen_statuses.add(review["status"])
    assert "awaiting_merge" in seen_statuses
    assert seen_statuses <= {"passed", "awaiting_merge"}


# --------------------------------------------------------------------------
# GitHub webhook
# --------------------------------------------------------------------------


def _webhook(client, event: str, payload: dict):
    return client.post("/api/webhooks/github", headers={"X-GitHub-Event": event}, json=payload)


def test_webhook_unregistered_repository_skipped(auth_client):
    client, _org = auth_client
    res = _webhook(
        client,
        "pull_request",
        {"action": "opened", "repository": {"full_name": "nobody/nothing"}, "pull_request": {"number": 1, "title": "x", "user": {"login": "a"}, "base": {"ref": "main"}}},
    )
    assert res.status_code == 200
    assert res.json()["skipped"] == "repository_not_registered"


def test_webhook_pull_request_opened_runs_review(auth_client):
    client, _org = auth_client
    repo = add_repo(client)

    res = _webhook(
        client,
        "pull_request",
        {
            "action": "opened",
            "repository": {"full_name": repo["full_name"]},
            "pull_request": {"number": 5, "title": "Add endpoint", "user": {"login": "octocat"}, "base": {"ref": "main"}},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "review_id" in body

    reviews = client.get("/api/pr-reviews").json()
    assert reviews["counts"]["all"] == 1


def test_webhook_auto_review_disabled_skips(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    client.patch(f"/api/repositories/{repo['id']}", json={"auto_review_enabled": False})

    res = _webhook(
        client,
        "pull_request",
        {"action": "opened", "repository": {"full_name": repo["full_name"]}, "pull_request": {"number": 1, "title": "x", "user": {"login": "a"}, "base": {"ref": "main"}}},
    )
    assert res.json()["skipped"] == "auto_review_disabled"


def test_webhook_synchronize_skipped_unless_rereview_on_push(auth_client):
    client, _org = auth_client
    repo = add_repo(client)

    payload = {
        "action": "synchronize",
        "repository": {"full_name": repo["full_name"]},
        "pull_request": {"number": 1, "title": "x", "user": {"login": "a"}, "base": {"ref": "main"}},
    }
    res = _webhook(client, "pull_request", payload)
    assert res.json()["skipped"] == "rereview_on_push_disabled"

    client.patch("/api/pr-reviews/settings", json={"rereview_on_push": True})
    res = _webhook(client, "pull_request", payload)
    assert "review_id" in res.json()


def test_webhook_target_branch_filter(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    client.patch("/api/pr-reviews/settings", json={"target_branches": ["release"]})

    payload = {
        "action": "opened",
        "repository": {"full_name": repo["full_name"]},
        "pull_request": {"number": 1, "title": "x", "user": {"login": "a"}, "base": {"ref": "main"}},
    }
    res = _webhook(client, "pull_request", payload)
    assert res.json()["skipped"] == "branch_not_targeted"

    payload["pull_request"]["base"]["ref"] = "release"
    res = _webhook(client, "pull_request", payload)
    assert "review_id" in res.json()


def test_webhook_excluded_username_and_bot_filters(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    client.patch("/api/pr-reviews/settings", json={"excluded_usernames": ["blockeduser"], "exclude_bot_accounts": True})

    blocked = _webhook(
        client,
        "pull_request",
        {"action": "opened", "repository": {"full_name": repo["full_name"]}, "pull_request": {"number": 1, "title": "x", "user": {"login": "blockeduser"}, "base": {"ref": "main"}}},
    )
    assert blocked.json()["skipped"] == "excluded_username"

    bot = _webhook(
        client,
        "pull_request",
        {"action": "opened", "repository": {"full_name": repo["full_name"]}, "pull_request": {"number": 2, "title": "x", "user": {"login": "renovate[bot]"}, "base": {"ref": "main"}}},
    )
    assert bot.json()["skipped"] == "excluded_bot_account"


def test_webhook_issue_comment_requires_strix_mention(auth_client):
    client, _org = auth_client
    repo = add_repo(client)

    no_mention = _webhook(
        client,
        "issue_comment",
        {"action": "created", "repository": {"full_name": repo["full_name"]}, "issue": {"number": 3, "title": "x", "user": {"login": "a"}, "pull_request": {}}, "comment": {"body": "looks good"}},
    )
    assert no_mention.json()["skipped"] == "no_strix_mention"

    with_mention = _webhook(
        client,
        "issue_comment",
        {"action": "created", "repository": {"full_name": repo["full_name"]}, "issue": {"number": 3, "title": "x", "user": {"login": "a"}, "pull_request": {}}, "comment": {"body": "@strix please review"}},
    )
    assert "review_id" in with_mention.json()


def test_webhook_unhandled_event_skipped(auth_client):
    client, _org = auth_client
    res = _webhook(client, "push", {})
    assert res.status_code == 200
    assert res.json()["skipped"].startswith("unhandled_event")


def test_webhook_missing_repository_or_pr_number_skipped(auth_client):
    client, _org = auth_client
    res = _webhook(client, "pull_request", {"action": "opened", "repository": {}, "pull_request": {"user": {}, "base": {}}})
    assert res.json()["skipped"] == "missing_repository_or_pr_number"


def test_webhook_invalid_json_skipped(client):
    res = client.post("/api/webhooks/github", headers={"X-GitHub-Event": "pull_request", "content-type": "application/json"}, content=b"not json")
    assert res.status_code == 200
    assert res.json()["skipped"] == "invalid_json"


def test_webhook_bad_signature_rejected(auth_client, monkeypatch):
    client, _org = auth_client
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "github_app_id", "fake-app-id")
    monkeypatch.setattr(settings_module.settings, "github_app_private_key", "fake-key")
    monkeypatch.setattr(settings_module.settings, "github_webhook_secret", "shh")

    res = _webhook(client, "pull_request", {})
    assert res.status_code == 401
    assert res.json()["detail"] == "invalid_signature"


def test_webhook_org_without_repo_org_not_found_branch(auth_client, monkeypatch):
    """Covers the (currently unreachable in practice) org-not-found branch:
    a repository row whose org_id doesn't resolve to an Organization."""
    client, _org = auth_client
    repo = add_repo(client)

    from app import models
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(models.Repository, repo["id"])
        row.org_id = "orphaned-org-id"
        db.commit()
    finally:
        db.close()

    res = _webhook(
        client,
        "pull_request",
        {"action": "opened", "repository": {"full_name": repo["full_name"]}, "pull_request": {"number": 1, "title": "x", "user": {"login": "a"}, "base": {"ref": "main"}}},
    )
    assert res.json()["skipped"] == "org_not_found"
