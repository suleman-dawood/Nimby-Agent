"""Token endpoint tests."""


def test_balance_no_auth(client):
    resp = client.get("/api/tokens/balance")
    assert resp.status_code == 401


def test_balance_with_auth(client, auth_headers):
    resp = client.get("/api/tokens/balance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tokens_remaining" in data
    assert "tokens_used" in data
    assert isinstance(data["tokens_remaining"], int)


def test_history_with_auth(client, auth_headers):
    resp = client.get("/api/tokens/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "usage" in data
    assert isinstance(data["usage"], list)


def test_history_no_auth(client):
    resp = client.get("/api/tokens/history")
    assert resp.status_code == 401
