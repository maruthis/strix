from .conftest import add_member


def test_list_integrations_starts_all_disconnected(auth_client):
    client, _org = auth_client
    res = client.get("/api/integrations")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 7
    assert all(i["status"] == "not_connected" for i in body)
    assert all(i["account_label"] is None for i in body)
    github = next(i for i in body if i["provider"] == "github")
    assert github["category"] == "code"
    assert github["coming_soon"] is False
    msteams = next(i for i in body if i["provider"] == "msteams")
    assert msteams["coming_soon"] is True


def test_connect_and_disconnect_integration(auth_client):
    client, org = auth_client

    connect = client.post("/api/integrations/github/connect")
    assert connect.status_code == 200
    body = connect.json()
    assert body["status"] == "connected"
    assert body["account_label"] == org["name"].lower().replace(" ", "-")
    assert body["connected_at"]

    listing = client.get("/api/integrations").json()
    github = next(i for i in listing if i["provider"] == "github")
    assert github["status"] == "connected"

    disconnect = client.request("DELETE", "/api/integrations/github")
    assert disconnect.status_code == 200
    assert disconnect.json()["status"] == "not_connected"

    listing_after = client.get("/api/integrations").json()
    github_after = next(i for i in listing_after if i["provider"] == "github")
    assert github_after["status"] == "not_connected"


def test_connect_unknown_provider_404(auth_client):
    client, _org = auth_client
    res = client.post("/api/integrations/does-not-exist/connect")
    assert res.status_code == 404


def test_disconnect_unknown_provider_404(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/integrations/does-not-exist")
    assert res.status_code == 404


def test_connect_coming_soon_provider_rejected(auth_client):
    client, _org = auth_client
    res = client.post("/api/integrations/msteams/connect")
    assert res.status_code == 400
    assert res.json()["detail"] == "provider_not_yet_available"


def test_disconnect_never_connected_provider_is_a_noop(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/integrations/slack")
    assert res.status_code == 200
    assert res.json()["status"] == "not_connected"


def test_reconnecting_updates_existing_row_instead_of_duplicating(auth_client):
    client, _org = auth_client
    first = client.post("/api/integrations/jira/connect").json()
    second = client.post("/api/integrations/jira/connect").json()
    assert first["account_label"] == second["account_label"]

    listing = client.get("/api/integrations").json()
    assert sum(1 for i in listing if i["provider"] == "jira") == 1


def test_connect_and_disconnect_require_admin(auth_client):
    client, org = auth_client
    add_member(client, org)

    connect = client.post("/api/integrations/github/connect")
    assert connect.status_code == 403
    assert connect.json()["detail"] == "admin_required"

    # A member can still see the (all-disconnected) list.
    listing = client.get("/api/integrations").json()
    assert all(i["status"] == "not_connected" for i in listing)

    disconnect = client.request("DELETE", "/api/integrations/github")
    assert disconnect.status_code == 403
