"""SSE adapter for ADK agent streaming.

Converts ADK Runner events to the existing frontend SSE format:
  data: {"type": "token", "content": "..."}
  data: {"type": "tool_call", "tool": "...", "status": "calling"|"done"}
  data: {"type": "citations", "citations": [...]}
  data: [DONE]
"""

from __future__ import annotations

import json
import logging

from google.adk.runners import InMemoryRunner
from google.genai import types

from pipeline.llm_utils import normalize_citations, extract_citations

logger = logging.getLogger(__name__)

# Internal ADK events — hide from user
_HIDDEN_TOOLS = {"transfer_to_agent"}

_credentials_ready = False

# Persistent runner + sessions for conversation history
_runner = None
_sessions: set[str] = set()


def _ensure_credentials():
    """Ensure Google ADC + Vertex AI env vars are set for ADK."""
    global _credentials_ready
    if _credentials_ready:
        return

    import os
    import base64
    import tempfile

    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.environ.get("GCP_PROJECT", "gen-lang-client-0499400729"))
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.environ.get("GCP_LOCATION", "us-central1"))

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sa_b64 = os.environ.get("GOOGLE_SA_KEY")
        if sa_b64:
            sa_json = base64.b64decode(sa_b64).decode("utf-8")
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            tmp.write(sa_json)
            tmp.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
        elif os.environ.get("GOOGLE_SA_JSON"):
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            tmp.write(os.environ["GOOGLE_SA_JSON"])
            tmp.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name

    _credentials_ready = True


def _get_runner():
    """Get or create persistent runner (keeps conversation sessions alive)."""
    global _runner
    if _runner is None:
        from agents.planning_analyst import create_agent
        _runner = InMemoryRunner(agent=create_agent(), app_name="nimby")
    return _runner


async def stream_agent_response(pp_number: str, question: str, user_id: str):
    """Stream agent response as SSE events."""
    _ensure_credentials()

    runner = _get_runner()
    session_id = f"{user_id}_{pp_number}"

    # Create session only once per user+pp combo (preserves conversation history)
    if session_id not in _sessions:
        try:
            existing = await runner.session_service.get_session(
                app_name="nimby", user_id=user_id, session_id=session_id,
            )
            if existing is not None:
                _sessions.add(session_id)
            else:
                await runner.session_service.create_session(
                    app_name="nimby", user_id=user_id, session_id=session_id,
                )
                _sessions.add(session_id)
        except Exception as exc:
            logger.debug("Session lookup failed for %s: %s", session_id, exc)
            try:
                await runner.session_service.create_session(
                    app_name="nimby", user_id=user_id, session_id=session_id,
                )
            except Exception:
                pass
            _sessions.add(session_id)

    contextualized = f"[Proposal: {pp_number}] {question}"

    full_text = ""
    tool_citations = []
    active_tools = set()

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=contextualized)],
            ),
        ):
            # Tool call requests
            fn_calls = event.get_function_calls()
            if fn_calls:
                for call in fn_calls:
                    if call.name in _HIDDEN_TOOLS:
                        continue
                    active_tools.add(call.name)
                    yield _sse({"type": "tool_call", "tool": call.name, "status": "calling"})

            # Tool responses
            fn_responses = event.get_function_responses()
            if fn_responses:
                for resp in fn_responses:
                    if resp.name in _HIDDEN_TOOLS:
                        continue
                    active_tools.discard(resp.name)
                    yield _sse({"type": "tool_call", "tool": resp.name, "status": "done"})
                    _extract_tool_citations(resp, tool_citations, pp_number)

            # Text content
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        full_text += part.text
                        yield _sse({"type": "token", "content": part.text})

    except Exception as e:
        logger.error("Agent stream error pp=%s: %s", pp_number, str(e)[:300], exc_info=True)
        _sessions.discard(session_id)
        if not full_text:
            yield _sse({"type": "error", "content": f"Agent error: {str(e)[:100]}"})
            yield "data: [DONE]\n\n"
            return

    # Post-stream: prefer inline citations, fallback to tool citations
    full_text = normalize_citations(full_text)
    inline_citations = extract_citations(full_text)
    source_list = inline_citations if inline_citations else tool_citations

    seen = set()
    unique_cits = []
    for c in source_list:
        doc = c.get("document_title", "")
        page = c.get("page", 0)
        key = f"{doc}|{page}"
        if key not in seen:
            seen.add(key)
            unique_cits.append({"document_title": doc, "page": page})

    if unique_cits:
        yield _sse({"type": "citations", "citations": unique_cits})

    # Flush any stuck tool indicators
    for tool_name in active_tools:
        yield _sse({"type": "tool_call", "tool": tool_name, "status": "done"})

    yield "data: [DONE]\n\n"


def _extract_tool_citations(resp, tool_citations: list, pp_number: str):
    """Extract citation info from tool responses."""
    try:
        result = resp.response if isinstance(resp.response, dict) else {}

        if resp.name == "search_documents":
            for chunk in result.get("chunks", []):
                if chunk.get("document_title") and chunk.get("page_number"):
                    tool_citations.append({
                        "document_title": chunk["document_title"],
                        "page": chunk["page_number"],
                    })
            logger.info("search_documents → %d citations", len(result.get("chunks", [])))

        elif resp.name == "get_proposal_metadata":
            title = result.get("title")
            if title and "error" not in result:
                tool_citations.append({
                    "document_title": f"NSW Planning Portal — {title}",
                    "page": 0,
                })

        elif resp.name == "get_site_context":
            if "error" not in result:
                tool_citations.append({
                    "document_title": "NSW Government Spatial Data (ArcGIS)",
                    "page": 0,
                })

        elif resp.name == "check_compliance":
            tool_citations.append({
                "document_title": "LEP Compliance Check",
                "page": 0,
            })

    except Exception as e:
        logger.warning("Citation extraction failed for %s: %s", resp.name, e)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
