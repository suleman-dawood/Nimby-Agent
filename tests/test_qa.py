"""Q&A endpoint tests."""

import pytest


def test_suggestions(client, sample_pp_number):
    resp = client.get(f"/api/qa/{sample_pp_number}/suggestions")
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert isinstance(data["questions"], list)


def test_ask_stream(client, sample_pp_number):
    resp = client.post(
        "/api/qa/ask/stream",
        json={"pp_number": sample_pp_number, "question": "What is this proposal about?"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/event-stream")

    # Check we get at least some SSE data
    text = resp.text
    assert "data:" in text


@pytest.mark.skipif(
    not pytest.importorskip("google.adk", reason="google-adk not installed locally"),
    reason="google-adk not installed locally",
)
def test_agent_stream(client, sample_pp_number):
    resp = client.post(
        "/api/qa/agent/stream",
        json={"pp_number": sample_pp_number, "question": "What is the zoning?"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/event-stream")

    text = resp.text
    assert "data:" in text
    # Agent should include tool_call events
    assert "tool_call" in text or "token" in text
