def test_billing_defaults_to_trialing(auth_client):
    client, _org = auth_client
    res = client.get("/api/settings/billing")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "trialing"
    assert body["card_added"] is False


def test_add_card_activates_subscription(auth_client):
    client, _org = auth_client
    res = client.post("/api/settings/billing/add-card")
    assert res.status_code == 200
    body = res.json()
    assert body["card_added"] is True
    assert body["status"] == "active"


def test_list_invoices_empty_in_mock_mode(auth_client):
    client, _org = auth_client
    res = client.get("/api/settings/billing/invoices")
    assert res.status_code == 200
    assert res.json() == []
