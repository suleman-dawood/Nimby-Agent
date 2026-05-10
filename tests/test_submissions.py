"""Submission endpoint tests."""


def test_concerns(client):
    resp = client.get("/api/submissions/concerns")
    assert resp.status_code == 200
    data = resp.json()
    assert "concerns" in data
    assert isinstance(data["concerns"], list)
    assert len(data["concerns"]) > 0
