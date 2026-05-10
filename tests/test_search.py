"""Search endpoint tests."""


def test_geocode(client):
    resp = client.post("/api/search/geocode", json={"address": "Sydney NSW"})
    assert resp.status_code == 200
    data = resp.json()
    assert "lat" in data
    assert "lng" in data
    assert abs(data["lat"] - (-33.87)) < 1  # roughly Sydney
    assert abs(data["lng"] - 151.21) < 1


def test_nearby(client):
    # Sydney CBD
    resp = client.get("/api/search/nearby?lat=-33.8688&lng=151.2093&radius_km=50")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)
