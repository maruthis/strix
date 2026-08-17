from .conftest import add_repo


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
