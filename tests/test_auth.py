"""Auth endpoint tests."""


def test_google_auth_invalid_token(client):
    resp = client.post("/api/auth/google", json={"id_token": "invalid"})
    assert resp.status_code == 401


def test_me_no_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_auth(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@nimby.dev"
    assert "tokens_remaining" in data
    assert "tokens_used" in data


def test_me_invalid_jwt(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_me_expired_jwt(client):
    import jwt
    from datetime import datetime, timedelta, timezone
    payload = {
        "user_id": 1,
        "email": "test@nimby.dev",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
