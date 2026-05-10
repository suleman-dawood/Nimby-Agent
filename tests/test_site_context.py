"""Site context endpoint tests."""


def test_site_context_valid(client, sample_pp_with_context):
    resp = client.get(f"/api/site-context/{sample_pp_with_context}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pp_number"] == sample_pp_with_context
    assert "zoning" in data
    assert "bushfire_prone" in data
    assert "flood_planning" in data
    assert "heritage_state" in data
    assert isinstance(data["bushfire_prone"], bool)
    assert isinstance(data["flood_planning"], bool)


def test_site_context_invalid(client):
    resp = client.get("/api/site-context/PP-INVALID-999")
    assert resp.status_code == 404


def test_site_context_live_query(client):
    # Sydney CBD coordinates
    resp = client.get("/api/site-context/query/live?lat=-33.8688&lng=151.2093")
    assert resp.status_code == 200
    data = resp.json()
    assert "zoning" in data
    assert data["zoning"] is not None  # Sydney CBD should have zoning
