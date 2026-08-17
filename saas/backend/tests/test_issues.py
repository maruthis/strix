import time

from .conftest import add_repo


def _run_pentest_to_completion(client, repo, timeout: float = 5.0) -> dict:
    pentest = client.post("/api/pentests", json={"target_type": "repository", "target_id": repo["id"]}).json()
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/pentests/{pentest['id']}").json()
        if body["status"] == "completed":
            return pentest
        time.sleep(0.02)
    raise AssertionError("pentest did not complete")


def test_list_issues_empty(auth_client):
    client, _org = auth_client
    res = client.get("/api/issues")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["severity_counts"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
    assert body["status_counts"]["all"] == 0


def test_issue_lifecycle(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    _run_pentest_to_completion(client, repo)

    listing = client.get("/api/issues").json()
    assert len(listing["items"]) > 0
    issue = listing["items"][0]

    detail = client.get(f"/api/issues/{issue['id']}")
    assert detail.status_code == 200
    assert detail.json()["title"] == issue["title"]

    update = client.patch(f"/api/issues/{issue['id']}/status", json={"status": "fixed"})
    assert update.status_code == 200
    assert update.json()["status"] == "fixed"

    fixed = client.get("/api/issues?status_filter=fixed").json()
    assert any(i["id"] == issue["id"] for i in fixed["items"])


def test_update_issue_status_invalid_value(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    _run_pentest_to_completion(client, repo)
    issue = client.get("/api/issues").json()["items"][0]

    res = client.patch(f"/api/issues/{issue['id']}/status", json={"status": "not-a-real-status"})
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid_status"


def test_update_issue_status_not_found(auth_client):
    client, _org = auth_client
    res = client.patch("/api/issues/does-not-exist/status", json={"status": "fixed"})
    assert res.status_code == 404


def test_get_issue_not_found(auth_client):
    client, _org = auth_client
    res = client.get("/api/issues/does-not-exist")
    assert res.status_code == 404


def test_list_issues_severity_and_repository_filters(auth_client):
    client, _org = auth_client
    repo = add_repo(client)
    _run_pentest_to_completion(client, repo)

    by_repo = client.get(f"/api/issues?repository_id={repo['id']}").json()
    assert len(by_repo["items"]) > 0

    other_repo = add_repo(client, "acme/other")
    by_other_repo = client.get(f"/api/issues?repository_id={other_repo['id']}").json()
    assert by_other_repo["items"] == []

    any_severity = client.get("/api/issues?severity=critical").json()
    for item in any_severity["items"]:
        assert item["severity"] == "critical"


def test_list_issues_domain_id_filter(auth_client):
    from .conftest import add_domain

    client, _org = auth_client
    domain = add_domain(client)
    client.post(f"/api/domains/{domain['id']}/verify")

    pentest = client.post("/api/pentests", json={"target_type": "domain", "target_id": domain["id"]}).json()
    import time

    deadline = time.time() + 5
    while time.time() < deadline:
        if client.get(f"/api/pentests/{pentest['id']}").json()["status"] == "completed":
            break
        time.sleep(0.02)

    by_domain = client.get(f"/api/issues?domain_id={domain['id']}").json()
    assert len(by_domain["items"]) > 0
    for item in by_domain["items"]:
        assert item["domain_id"] == domain["id"]

    other_domain = add_domain(client, "other.example.com")
    by_other = client.get(f"/api/issues?domain_id={other_domain['id']}").json()
    assert by_other["items"] == []
