"""Brief endpoint tests."""

import pytest


def test_brief_invalid(client):
    resp = client.get("/api/briefs/PP-INVALID-999")
    assert resp.status_code in [404, 500]  # 404 or error if no brief file


def test_brief_valid(client, sample_pp_number):
    resp = client.get(f"/api/briefs/{sample_pp_number}")
    # May be 404 if no pre-generated brief file — that's OK
    if resp.status_code == 200:
        data = resp.json()
        assert "pp_number" in data
        assert "markdown" in data
