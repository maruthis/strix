def test_create_list_delete_webhook(auth_client):
    client, _org = auth_client

    res = client.post("/api/settings/webhooks", json={"url": "https://example.com/hook"})
    assert res.status_code == 200
    webhook = res.json()
    assert webhook["events"] == ["pentest.completed", "issue.created", "pr_review.completed"]
    assert webhook["secret"]

    listing = client.get("/api/settings/webhooks").json()
    assert len(listing) == 1

    delete = client.request("DELETE", f"/api/settings/webhooks/{webhook['id']}")
    assert delete.status_code == 200
    assert client.get("/api/settings/webhooks").json() == []


def test_delete_webhook_not_found(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/settings/webhooks/does-not-exist")
    assert res.status_code == 404
