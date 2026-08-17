def test_create_list_revoke_token(auth_client):
    client, _org = auth_client

    res = client.post("/api/settings/tokens", json={"name": "CI token"})
    assert res.status_code == 200
    body = res.json()
    assert body["token"].startswith("strix_")
    assert body["token_prefix"] == body["token"][:12]
    assert body["expires_at"] is not None  # defaults to 90 days

    listing = client.get("/api/settings/tokens").json()
    assert len(listing) == 1
    assert "token" not in listing[0]

    revoke = client.request("DELETE", f"/api/settings/tokens/{body['id']}")
    assert revoke.status_code == 200

    listing_after = client.get("/api/settings/tokens").json()
    assert listing_after[0]["status"] == "revoked"


def test_revoke_token_not_found(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/settings/tokens/does-not-exist")
    assert res.status_code == 404


def test_create_token_with_custom_scopes_and_expiration(auth_client):
    client, _org = auth_client
    res = client.post(
        "/api/settings/tokens",
        json={"name": "Full access", "scopes": ["scans:read", "scans:write", "assets:read"], "expires_in_days": 30},
    )
    body = res.json()
    assert body["scopes"] == ["scans:read", "scans:write", "assets:read"]
    assert body["expires_at"] is not None


def test_create_token_with_no_expiration(auth_client):
    client, _org = auth_client
    res = client.post("/api/settings/tokens", json={"name": "Long-lived", "expires_in_days": None})
    assert res.json()["expires_at"] is None
