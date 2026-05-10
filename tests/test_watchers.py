"""Watcher endpoint tests."""


def test_create_watcher_no_auth(client):
    resp = client.post("/api/watchers", json={
        "address": "1 Test St, Sydney NSW",
        "lat": -33.87,
        "lng": 151.21,
        "radius_km": 5.0,
    })
    assert resp.status_code == 401


def test_create_watcher_with_auth(client, auth_headers):
    resp = client.post("/api/watchers", json={
        "address": "1 Test St, Sydney NSW",
        "lat": -33.87,
        "lng": 151.21,
        "radius_km": 5.0,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["address"] == "1 Test St, Sydney NSW"
    assert data["radius_km"] == 5.0
    assert data["active"] is True


def test_list_watchers(client, auth_headers):
    resp = client.get("/api/watchers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_delete_watcher(client, auth_headers):
    # Create one first
    create_resp = client.post("/api/watchers", json={
        "address": "Delete Me St, Sydney NSW",
        "lat": -33.87,
        "lng": 151.21,
        "radius_km": 3.0,
    }, headers=auth_headers)
    watcher_id = create_resp.json()["id"]

    # Delete it
    resp = client.delete(f"/api/watchers/{watcher_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


def test_notifications(client, auth_headers):
    # Create watcher first
    create_resp = client.post("/api/watchers", json={
        "address": "Notif Test St, Sydney NSW",
        "lat": -33.87,
        "lng": 151.21,
        "radius_km": 5.0,
    }, headers=auth_headers)
    watcher_id = create_resp.json()["id"]

    resp = client.get(f"/api/watchers/{watcher_id}/notifications", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
