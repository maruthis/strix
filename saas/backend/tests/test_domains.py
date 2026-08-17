from .conftest import add_domain


def test_list_domains_empty(auth_client):
    client, _org = auth_client
    assert client.get("/api/domains").json() == []


def test_add_domain_conflict(auth_client):
    client, _org = auth_client
    add_domain(client, "app.example.com")
    res = client.post("/api/domains", json={"hostname": "app.example.com"})
    assert res.status_code == 409
    assert res.json()["detail"] == "already_added"


def test_get_domain(auth_client):
    client, _org = auth_client
    domain = add_domain(client)
    res = client.get(f"/api/domains/{domain['id']}")
    assert res.status_code == 200
    assert res.json()["hostname"] == domain["hostname"]


def test_get_domain_not_found(auth_client):
    client, _org = auth_client
    res = client.get("/api/domains/does-not-exist")
    assert res.status_code == 404


def test_scan_blocked_until_verified(auth_client):
    client, _org = auth_client
    domain = add_domain(client)

    res = client.post(f"/api/domains/{domain['id']}/scan")
    assert res.status_code == 400
    assert res.json()["detail"] == "domain_not_verified"

    verify = client.post(f"/api/domains/{domain['id']}/verify")
    assert verify.status_code == 200
    assert verify.json()["verified"] is True

    res = client.post(f"/api/domains/{domain['id']}/scan")
    assert res.status_code == 200
    assert "pentest_id" in res.json()


def test_scan_domain_not_found(auth_client):
    client, _org = auth_client
    res = client.post("/api/domains/does-not-exist/scan")
    assert res.status_code == 404


def test_remove_domain(auth_client):
    client, _org = auth_client
    domain = add_domain(client)
    res = client.request("DELETE", f"/api/domains/{domain['id']}")
    assert res.status_code == 200
    assert client.get("/api/domains").json() == []


def test_remove_domain_not_found(auth_client):
    client, _org = auth_client
    res = client.request("DELETE", "/api/domains/does-not-exist")
    assert res.status_code == 404


def test_verify_domain_not_found(auth_client):
    client, _org = auth_client
    res = client.post("/api/domains/does-not-exist/verify")
    assert res.status_code == 404
