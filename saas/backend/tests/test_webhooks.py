def test_create_list_delete_webhook(auth_client):
    client, _org = auth_client

    res = client.post("/api/settings/webhooks", json={"url": "https://example.com/hook"})
    assert res.status_code == 200
    webhook = res.json()
    assert webhook["events"] == ["pentest.completed", "issue.created", "pr_review.completed"]
    assert webhook["secret"]  # shown once, at creation

    listing = client.get("/api/settings/webhooks").json()
    assert len(listing) == 1
    assert "secret" not in listing[0]  # never re-exposed after creation

    delete = client.request("DELETE", f"/api/settings/webhooks/{webhook['id']}")
    assert delete.status_code == 200
    assert client.get("/api/settings/webhooks").json() == []


def test_delete_webhook_not_found(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/settings/webhooks/does-not-exist")
    assert res.status_code == 404


def test_create_and_delete_webhook_require_admin(auth_client):
    from .conftest import add_member

    client, org = auth_client
    admin_webhook = client.post("/api/settings/webhooks", json={"url": "https://example.com/hook"}).json()

    add_member(client, org)
    create = client.post("/api/settings/webhooks", json={"url": "https://attacker.example.com/exfil"})
    assert create.status_code == 403
    assert create.json()["detail"] == "admin_required"

    delete = client.request("DELETE", f"/api/settings/webhooks/{admin_webhook['id']}")
    assert delete.status_code == 403

    # A member can still see the (secret-free) list.
    listing = client.get("/api/settings/webhooks").json()
    assert len(listing) == 1
    assert "secret" not in listing[0]
