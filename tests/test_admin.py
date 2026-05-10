"""Admin endpoint tests."""


def test_batch_status(client):
    resp = client.get("/api/admin/batch-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ["never_started", "running", "completed", "failed"]
