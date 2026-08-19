def test_audit_log_records_actions(auth_client):
    client, org = auth_client

    client.patch("/api/orgs/current", json={"name": "Renamed Co"})
    client.post("/api/members/invitations", json={"email": "someone@example.com", "role": "member"})

    res = client.get("/api/settings/audit-logs")
    assert res.status_code == 200
    body = res.json()
    entries = body["items"]
    actions = [e["action"] for e in entries]
    assert "org.created" in actions
    assert "org.renamed" in actions
    assert "member.invited" in actions
    assert all(e["actor_email"] == "user@example.com" for e in entries)


def test_audit_log_empty_for_fresh_org_action_free(client):
    from .conftest import otp_login, create_org

    otp_login(client, "quiet@example.com")
    create_org(client, "Quiet Co")
    body = client.get("/api/settings/audit-logs").json()
    # org.created itself is logged, so there's always at least one entry.
    assert body["total"] == 1
    assert body["items"][0]["action"] == "org.created"


def test_audit_log_requires_admin(auth_client):
    client, org = auth_client
    # Downgrade the caller to a plain member of their own org to confirm
    # the endpoint is now admin-gated (it used to be open to any member).
    from app import models
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        membership = db.query(models.Membership).filter_by(org_id=org["id"]).first()
        membership.role = "member"
        db.commit()
    finally:
        db.close()

    res = client.get("/api/settings/audit-logs")
    assert res.status_code == 403


def test_request_log_records_mutating_and_error_requests(auth_client):
    client, org = auth_client

    client.patch("/api/orgs/current", json={"name": "Renamed Again"})
    client.get("/api/pentests/does-not-exist")  # 404, should be logged despite being a GET

    res = client.get("/api/settings/request-logs")
    assert res.status_code == 200
    body = res.json()
    paths = [(e["method"], e["status_code"], e["path"]) for e in body["items"]]
    assert ("PATCH", 200, "/api/orgs/current") in paths
    assert ("GET", 404, "/api/pentests/does-not-exist") in paths
    # A plain, successful GET must never appear.
    assert not any(method == "GET" and status_code < 400 for method, status_code, _ in paths)
