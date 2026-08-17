def test_audit_log_records_actions(auth_client):
    client, org = auth_client

    client.patch("/api/orgs/current", json={"name": "Renamed Co"})
    client.post("/api/members/invitations", json={"email": "someone@example.com", "role": "member"})

    res = client.get("/api/settings/audit-logs")
    assert res.status_code == 200
    entries = res.json()
    actions = [e["action"] for e in entries]
    assert "org.created" in actions
    assert "org.renamed" in actions
    assert "member.invited" in actions
    assert all(e["actor_email"] == "user@example.com" for e in entries)


def test_audit_log_empty_for_fresh_org_action_free(client):
    from .conftest import otp_login, create_org

    otp_login(client, "quiet@example.com")
    create_org(client, "Quiet Co")
    entries = client.get("/api/settings/audit-logs").json()
    # org.created itself is logged, so there's always at least one entry.
    assert len(entries) == 1
    assert entries[0]["action"] == "org.created"
