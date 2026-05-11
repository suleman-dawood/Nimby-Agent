"""Subscription and in-app notification endpoint tests."""


def test_subscribe_no_auth(client):
    resp = client.post("/api/subscriptions", json={"pp_number": "PP-2023-2828"})
    assert resp.status_code == 401


def test_subscribe_with_auth(client, auth_headers, sample_pp_number):
    resp = client.post("/api/subscriptions", json={
        "pp_number": sample_pp_number,
        "notify_docs": True,
        "notify_stage": True,
        "notify_expiry": True,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pp_number"] == sample_pp_number
    assert data["active"] is True
    assert data["notify_docs"] is True


def test_list_subscriptions(client, auth_headers):
    resp = client.get("/api/subscriptions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_unsubscribe(client, auth_headers, sample_pp_number):
    # Subscribe first
    client.post("/api/subscriptions", json={
        "pp_number": sample_pp_number,
    }, headers=auth_headers)

    # Unsubscribe
    resp = client.delete(f"/api/subscriptions/{sample_pp_number}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "unsubscribed"


def test_notifications_empty(client, auth_headers):
    resp = client.get("/api/subscriptions/notifications", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_unread_count(client, auth_headers):
    resp = client.get("/api/subscriptions/notifications/unread", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["count"], int)


def test_mark_all_read(client, auth_headers):
    resp = client.post("/api/subscriptions/notifications/read-all", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "all_read"


def test_notifications_no_auth(client):
    resp = client.get("/api/subscriptions/notifications")
    assert resp.status_code == 401


def test_unread_no_auth(client):
    resp = client.get("/api/subscriptions/notifications/unread")
    assert resp.status_code == 401
