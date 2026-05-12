"""Multi-agent planning analysis system built on Google ADK.

Architecture:
  Root Orchestrator (gemini-2.5-pro) — routes questions to specialist agents
  ├── Document Analyst    — RAG search over proposal PDFs
  ├── Site Intelligence   — spatial data, zoning, hazards, nearby places
  └── Compliance Checker  — cross-references proposal vs LEP controls
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

# --- Specialist Agents ---

document_analyst = Agent(
    name="document_analyst",
    model="gemini-2.5-flash",
    description="Searches and analyses planning proposal documents (PDFs). "
    "Use for questions about what the proposal says, traffic studies, shadow diagrams, "
    "environmental reports, building heights, and any content from uploaded documents.",
    instruction="""\
You are a document analysis specialist for NSW planning proposals.
Your job is to search proposal documents and extract specific evidence.

Rules:
- Always cite sources using [doc: Title | p.N] format
- Quote specific numbers, measurements, and findings from documents
- If no documents are found, say so clearly — do not guess
- Be precise and factual — your evidence may be used in formal submissions
""",
    tools=[search_documents],
)

site_intelligence = Agent(
    name="site_intelligence",
    model="gemini-2.5-flash",
    description="Provides planning controls, zoning, hazard data, and nearby amenities. "
    "Use for questions about zoning, building height limits, FSR, heritage, bushfire, "
    "flood risk, environmental constraints, or what's nearby (schools, hospitals, parks).",
    instruction="""\
You are a site intelligence specialist for NSW planning.
You provide authoritative data from NSW government spatial layers and Google Places.

Data sources:
- 14 NSW ArcGIS REST API layers (zoning, height, FSR, heritage, bushfire, flood, etc.)
- Google Places API (schools, hospitals, parks, transit)

Rules:
- Always state the source (e.g. "According to NSW Planning Portal spatial data...")
- Reference zone codes (e.g. R2 Low Density Residential)
- Proactively flag hazards (bushfire, flood, landslide) if present
- When comparing addresses, query both locations and highlight differences
""",
    tools=[get_site_context, query_spatial_layer, get_nearby_places],
)

compliance_checker = Agent(
    name="compliance_checker",
    model="gemini-2.5-flash",
    description="Checks whether a planning proposal complies with the Local Environmental Plan (LEP). "
    "Use for questions about compliance, permissibility, whether something is allowed, "
    "or how the proposal compares to current planning controls.",
    instruction="""\
You are a compliance analysis specialist for NSW planning.
You compare what a proposal seeks against current LEP planning controls.

Rules:
- Always compare specific numbers (e.g. "LEP allows 14m, proposal seeks 24m")
- Reference the relevant LEP clause and zone code
- Flag any non-compliance or inconsistencies clearly
- Distinguish between "inconsistent with LEP" and "seeks to amend LEP"
  (planning proposals often intentionally seek changes to controls)
""",
    tools=[check_compliance, get_site_context, search_documents],
)

# --- Root Orchestrator ---

ORCHESTRATOR_PROMPT = """\
You are the lead planning analyst for NSW planning proposals.
You coordinate a team of specialist agents to answer resident questions.

Your specialists:
- document_analyst: Searches proposal PDFs for evidence and specific content
- site_intelligence: Provides zoning, planning controls, hazards, nearby amenities
  from NSW government spatial data
- compliance_checker: Cross-references proposals against LEP controls

Routing:
- "What does the proposal say about X?" → document_analyst
- "What's the zoning?" / "Any flood risk?" / "Schools nearby?" → site_intelligence
- "Is this compliant?" / "Does this exceed height limits?" → compliance_checker
- Complex questions → delegate to multiple specialists, then synthesise

Rules:
- Always cite document sources using [doc: Title | p.N] format
- Be concise and factual — residents need clear, actionable information
- Proactively mention relevant hazards or compliance issues
- For proposals without documents, use site_intelligence and get_proposal_metadata

Important: Some proposals may have no public documents yet.
If document_analyst finds nothing:
- Use site_intelligence for planning controls and hazards
- Use get_proposal_metadata for basic proposal info
- Explain what stage the proposal is at
- Suggest subscribing for notifications when documents become available
"""


def create_agent() -> Agent:
    """Create the multi-agent planning analysis system."""
    return Agent(
        name="planning_orchestrator",
        model="gemini-2.5-pro",
        instruction=ORCHESTRATOR_PROMPT,
        tools=[get_proposal_metadata],
        sub_agents=[document_analyst, site_intelligence, compliance_checker],
    )
