"""Multi-agent planning analysis system built on Google ADK.

Architecture (all gemini-2.5-pro):
  Root Orchestrator — routes questions to specialist agents
  ├── Document Analyst    — RAG search over proposal PDFs
  ├── Site Intelligence   — spatial data, zoning, hazards, nearby places
  └── Compliance Checker  — cross-references proposal vs LEP controls

Prompts are loaded from pipeline/prompts/agent_*.md for easy iteration.
"""

from __future__ import annotations

from google.adk.agents import Agent

from agents.tools import (
    check_compliance,
    get_nearby_places,
    get_proposal_metadata,
    get_site_context,
    query_spatial_layer,
    search_documents,
)
from pipeline.llm_utils import load_prompt

# --- Specialist Agents ---

document_analyst = Agent(
    name="document_analyst",
    model="gemini-2.5-pro",
    description="Searches and analyses planning proposal documents (PDFs). "
    "Use for questions about what the proposal says, traffic studies, shadow diagrams, "
    "environmental reports, building heights, and any content from uploaded documents.",
    instruction=load_prompt("agent_document_analyst"),
    tools=[search_documents],
)

site_intelligence = Agent(
    name="site_intelligence",
    model="gemini-2.5-pro",
    description="Provides planning controls, zoning, hazard data, and nearby amenities. "
    "Use for questions about zoning, building height limits, FSR, heritage, bushfire, "
    "flood risk, environmental constraints, or what's nearby (schools, hospitals, parks).",
    instruction=load_prompt("agent_site_intelligence"),
    tools=[get_site_context, query_spatial_layer, get_nearby_places],
)

compliance_checker = Agent(
    name="compliance_checker",
    model="gemini-2.5-pro",
    description="Checks whether a planning proposal complies with the Local Environmental Plan (LEP). "
    "Use for questions about compliance, permissibility, whether something is allowed, "
    "or how the proposal compares to current planning controls.",
    instruction=load_prompt("agent_compliance_checker"),
    tools=[check_compliance, get_site_context, search_documents],
)

# --- Root Orchestrator ---


def create_agent() -> Agent:
    """Create the multi-agent planning analysis system."""
    return Agent(
        name="planning_orchestrator",
        model="gemini-2.5-pro",
        instruction=load_prompt("agent_orchestrator"),
        tools=[get_proposal_metadata],
        sub_agents=[document_analyst, site_intelligence, compliance_checker],
    )
