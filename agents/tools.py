"""Tool functions for the Planning Analyst ADK agent.

Each function is auto-wrapped as a FunctionTool by ADK.
Docstrings become tool descriptions the LLM sees.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def search_documents(pp_number: str, query: str, k: int = 8) -> dict:
    """Search proposal documents using hybrid retrieval (pgvector + BM25 + Cohere rerank).

    Use this when the user asks about what the proposal says, traffic studies,
    shadow analysis, building heights mentioned in documents, environmental reports, etc.

    Args:
        pp_number: The planning proposal number (e.g. PP-2023-2828)
        query: The search query describing what to look for
        k: Number of results to return (default 8)

    Returns:
        dict with 'chunks' list containing text, page_number, document_title
    """
    start = time.perf_counter()
    from pipeline.retrieve import retrieve
    chunks = retrieve(pp_number, query, k=k, tier_filter=[1, 2])
    ms = (time.perf_counter() - start) * 1000
    logger.info("search_documents pp=%s q='%s' → %d chunks (%.0fms)", pp_number, query[:40], len(chunks), ms)
    return {
        "chunks": [
            {
                "text": c["text"][:1500],
                "page_number": c["page_number"],
                "document_title": c["document_title"],
            }
            for c in chunks
        ],
        "total_found": len(chunks),
    }


def get_proposal_metadata(pp_number: str) -> dict:
    """Get basic proposal information: title, council, addresses, dates, stage, description.

    Use this when the user asks general questions about a proposal like
    "what is this proposal about?" or "when does exhibition end?"

    Args:
        pp_number: The planning proposal number (e.g. PP-2023-2828)

    Returns:
        dict with proposal metadata
    """
    start = time.perf_counter()
    from scraper.models import PP, create_db_engine, create_session
    engine = create_db_engine()
    session = create_session(engine)
    try:
        pp = session.get(PP, pp_number)
        if not pp:
            logger.warning("get_proposal_metadata: %s not found", pp_number)
            return {"error": f"Proposal {pp_number} not found"}
        ms = (time.perf_counter() - start) * 1000
        logger.info("get_proposal_metadata pp=%s → %s (%.0fms)", pp_number, pp.title[:40] if pp.title else "?", ms)
        return {
            "pp_number": pp.pp_number,
            "title": pp.title,
            "council": pp.council,
            "addresses": pp.addresses,
            "description": (pp.description or "")[:2000],
            "stage": pp.stage,
            "exhibition_start": str(pp.exhibition_start) if pp.exhibition_start else None,
            "exhibition_end": str(pp.exhibition_end) if pp.exhibition_end else None,
            "relevant_planning_authority": pp.relevant_planning_authority,
        }
    finally:
        session.close()


def get_site_context(pp_number: str) -> dict:
    """Get planning controls for the proposal site from NSW government data.

    Returns zoning, max building height, FSR, heritage listings, hazards
    (bushfire, flood, landslide), and environmental constraints.
    This data is pre-computed from NSW ArcGIS APIs — zero cost.

    Use this for any question about planning rules, zoning, compliance,
    or site constraints.

    Args:
        pp_number: The planning proposal number

    Returns:
        dict with zoning, height limits, heritage, hazards, environmental data
    """
    start = time.perf_counter()
    from scraper.models import SiteContext, create_db_engine, create_session
    engine = create_db_engine()
    session = create_session(engine)
    try:
        ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()
        if not ctx:
            logger.warning("get_site_context: no data for %s", pp_number)
            return {"error": "No site context available for this proposal"}
        ms = (time.perf_counter() - start) * 1000
        logger.info("get_site_context pp=%s → zone=%s (%.0fms)", pp_number, ctx.zoning, ms)
        return {
            "zoning": ctx.zoning,
            "max_height_m": ctx.max_height_m,
            "max_fsr": ctx.max_fsr,
            "min_lot_size_sqm": ctx.min_lot_size_sqm,
            "heritage_item": ctx.heritage_item,
            "heritage_state": ctx.heritage_state,
            "bushfire_prone": ctx.bushfire_prone,
            "bushfire_category": ctx.bushfire_category,
            "flood_planning": ctx.flood_planning,
            "landslide_risk": ctx.landslide_risk,
            "acid_sulfate_class": ctx.acid_sulfate_class,
            "biodiversity_sensitive": ctx.biodiversity_sensitive,
            "drinking_water_catchment": ctx.drinking_water_catchment,
            "wetlands_nearby": ctx.wetlands_nearby,
            "environmentally_sensitive": ctx.environmentally_sensitive,
        }
    finally:
        session.close()


def query_spatial_layer(lat: float, lng: float, layer: str) -> dict:
    """Query NSW government planning data for any address by coordinates.

    Use this when comparing zoning or controls between the user's address
    and the proposal site, or checking planning data for a specific location.

    Args:
        lat: Latitude of the location
        lng: Longitude of the location
        layer: Which data layer to query. Options: zoning, height, fsr,
               heritage_local, heritage_state, bushfire, flood, landslide,
               acid_sulfate, biodiversity, drinking_water, wetlands, env_sensitive

    Returns:
        dict with the raw attributes from the NSW ArcGIS layer
    """
    from pipeline.spatial import query_layer, LAYERS
    if layer not in LAYERS:
        return {"error": f"Unknown layer '{layer}'. Options: {list(LAYERS.keys())}"}
    service, layer_id = LAYERS[layer]
    attrs = query_layer(lat, lng, service, layer_id)
    if attrs is None:
        return {"result": "No data found at this location for the requested layer"}
    return {"layer": layer, "attributes": attrs}


def check_compliance(pp_number: str) -> dict:
    """Compare what the proposal wants against the current LEP planning controls.

    Checks the proposal description against the site's zoning, height limits,
    FSR, and heritage status. Flags potential non-compliance.

    Use when the user asks about compliance, whether something is permitted,
    or if the proposal is consistent with the LEP.

    Args:
        pp_number: The planning proposal number

    Returns:
        dict with compliance flags and site context
    """
    metadata = get_proposal_metadata(pp_number)
    context = get_site_context(pp_number)

    if "error" in metadata or "error" in context:
        return {"error": "Cannot check compliance — missing data",
                "metadata": metadata, "site_context": context}

    return {
        "proposal": {
            "title": metadata.get("title"),
            "description": metadata.get("description", "")[:1000],
        },
        "current_controls": context,
        "note": "Compare the proposal description against the current controls. "
                "Flag any proposed changes that exceed current LEP limits.",
    }


def get_nearby_places(lat: float, lng: float, place_types: str, radius_m: int = 1000) -> dict:
    """Find schools, hospitals, parks, and transit near a location using Google Places API.

    Use when discussing community impact — what amenities or sensitive receivers
    are near the proposal site.

    Args:
        lat: Latitude
        lng: Longitude
        place_types: Comma-separated place types (e.g. "school,hospital,park")
        radius_m: Search radius in meters (default 1000)

    Returns:
        dict with list of nearby places
    """
    import httpx
    import os

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("NEXT_PUBLIC_GOOGLE_MAPS_KEY")
    if not api_key:
        return {"error": "Google Maps API key not configured"}

    types_list = [t.strip() for t in place_types.split(",")]
    all_places = []

    for ptype in types_list[:4]:  # limit to 4 types
        try:
            resp = httpx.post(
                "https://places.googleapis.com/v1/places:searchNearby",
                headers={
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "places.displayName,places.types,places.formattedAddress,places.location",
                },
                json={
                    "includedTypes": [ptype],
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": lat, "longitude": lng},
                            "radius": float(radius_m),
                        }
                    },
                    "maxResultCount": 5,
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                for place in data.get("places", []):
                    all_places.append({
                        "name": place.get("displayName", {}).get("text", "Unknown"),
                        "type": ptype,
                        "address": place.get("formattedAddress", ""),
                    })
        except Exception as e:
            logger.warning("Places API error for type %s: %s", ptype, e)

    return {"places": all_places, "radius_m": radius_m}
