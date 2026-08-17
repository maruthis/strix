def test_create_list_revoke_token(auth_client):
    client, _org = auth_client

    res = client.post("/api/settings/tokens", json={"name": "CI token"})
    assert res.status_code == 200
    body = res.json()
    assert body["token"].startswith("strix_")
    assert body["token_prefix"] == body["token"][:12]

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
