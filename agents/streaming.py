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
import asyncio

from google.adk.runners import InMemoryRunner
from google.genai import types

from pipeline.llm_utils import normalize_citations, extract_citations

logger = logging.getLogger(__name__)


_credentials_ready = False


def _ensure_credentials():
    """Ensure Google ADC + Vertex AI env vars are set for ADK."""
    global _credentials_ready
    if _credentials_ready:
        return

    import os
    import base64
    import tempfile

    # Set Vertex AI env vars for ADK
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.environ.get("GCP_PROJECT", "gen-lang-client-0499400729"))
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.environ.get("GCP_LOCATION", "us-central1"))

    # Set ADC credentials from service account (same as pipeline/llm_utils.py)
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


async def stream_agent_response(pp_number: str, question: str, user_id: str):
    """Stream agent response as SSE events.

    Yields SSE-formatted strings compatible with the existing frontend.
    """
    _ensure_credentials()

    from agents.planning_analyst import create_agent

    agent = create_agent()
    app_name = "nimby"
    session_id = f"{user_id}_{pp_number}"

    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session_service = runner.session_service

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    # Contextualize the question with the PP number
    contextualized = f"[Proposal: {pp_number}] {question}"

    full_text = ""
    tool_citations = []  # Citations from search_documents tool results

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
                yield _sse({"type": "tool_call", "tool": call.name, "status": "calling"})

        # Tool responses (tool finished) — extract citations from search results
        fn_responses = event.get_function_responses()
        if fn_responses:
            for resp in fn_responses:
                yield _sse({"type": "tool_call", "tool": resp.name, "status": "done"})
                # Capture citations from search_documents results
                if resp.name == "search_documents":
                    try:
                        # Debug: log the response structure
                        logger.info("search_documents resp type=%s", type(resp.response))
                        logger.info("search_documents resp=%s", str(resp.response)[:500])
                        result = resp.response if isinstance(resp.response, dict) else {}
                        for chunk in result.get("chunks", []):
                            if chunk.get("document_title") and chunk.get("page_number"):
                                tool_citations.append({
                                    "document_title": chunk["document_title"],
                                    "page": chunk["page_number"],
                                })
                        logger.info("Extracted %d tool citations", len(tool_citations))
                    except Exception as e:
                        logger.warning("Failed to extract tool citations: %s", e)
                elif resp.name == "get_proposal_metadata":
                    logger.info("get_proposal_metadata resp type=%s", type(resp.response))

        # Text content (streaming or final)
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    full_text += part.text
                    yield _sse({"type": "token", "content": part.text})

    # Post-stream: merge inline citations + tool citations
    full_text = normalize_citations(full_text)
    inline_citations = extract_citations(full_text)

    seen = set()
    unique_cits = []
    for c in inline_citations + tool_citations:
        doc = c.get("document_title", "")
        page = c.get("page", 0)
        key = f"{doc}|{page}"
        if key not in seen:
            seen.add(key)
            unique_cits.append({"document_title": doc, "page": page})

    if unique_cits:
        yield _sse({"type": "citations", "citations": unique_cits})

    yield "data: [DONE]\n\n"


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
