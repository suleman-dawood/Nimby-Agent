"""NSW ArcGIS REST API client for planning spatial data.

Queries free, no-auth NSW government spatial layers by lat/lng.
Returns structured planning controls, hazards, and environmental data.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

ARCGIS_BASE = "https://mapprod3.environment.nsw.gov.au/arcgis/rest/services"

# (service_path, layer_id)
LAYERS = {
    "zoning": ("ePlanning/Planning_Portal_Principal_Planning", 19),
    "height": ("ePlanning/Planning_Portal_Principal_Planning", 14),
    "fsr": ("ePlanning/Planning_Portal_Principal_Planning", 11),
    "lot_size": ("ePlanning/Planning_Portal_Principal_Planning", 22),
    "heritage_local": ("ePlanning/Planning_Portal_Principal_Planning", 16),
    "heritage_state": ("ePlanning/Planning_Portal_Principal_Planning", 221),
    "bushfire": ("ePlanning/Planning_Portal_Hazard", 229),
    "flood": ("ePlanning/Planning_Portal_Hazard", 230),
    "landslide": ("ePlanning/Planning_Portal_Hazard", 232),
    "acid_sulfate": ("ePlanning/Planning_Portal_Protection", 234),
    "biodiversity": ("ePlanning/Planning_Portal_Protection", 243),
    "drinking_water": ("ePlanning/Planning_Portal_Protection", 236),
    "wetlands": ("ePlanning/Planning_Portal_Protection", 244),
    "env_sensitive": ("ePlanning/Planning_Portal_Protection", 245),
}


def query_layer(lat: float, lng: float, service: str, layer_id: int) -> dict | None:
    """Query a single ArcGIS layer by point. Returns first feature's attributes or None."""
    url = f"{ARCGIS_BASE}/{service}/MapServer/{layer_id}/query"
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if features:
            return features[0].get("attributes")
        return None
    except Exception as e:
        logger.warning("ArcGIS query failed for %s layer %d: %s", service, layer_id, e)
        return None


def _parse_height(lay_class: str | None) -> float | None:
    """Parse height string like 'J - 14 Metres' → 14.0"""
    if not lay_class:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:metres|meters|m)", lay_class, re.I)
    return float(m.group(1)) if m else None


def _parse_fsr(lay_class: str | None) -> float | None:
    """Parse FSR string like 'N - 0.6:1' → 0.6"""
    if not lay_class:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*:\s*1", lay_class)
    return float(m.group(1)) if m else None


def _parse_lot_size(lay_class: str | None) -> float | None:
    """Parse lot size string like '450 square metres' → 450.0"""
    if not lay_class:
        return None
    m = re.search(r"(\d+(?:,\d+)?(?:\.\d+)?)", lay_class)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _parse_acid_sulfate_class(lay_class: str | None) -> int | None:
    """Parse acid sulfate class like 'Class 3' → 3"""
    if not lay_class:
        return None
    m = re.search(r"class\s*(\d)", lay_class, re.I)
    return int(m.group(1)) if m else None


def query_all_layers(lat: float, lng: float) -> dict:
    """Query all planning layers for a location. Returns dict for SiteContext fields."""
    raw = {}
    results = {}

    for name, (service, layer_id) in LAYERS.items():
        attrs = query_layer(lat, lng, service, layer_id)
        raw[name] = attrs
        time.sleep(0.3)  # polite rate limiting

    # Parse zoning
    z = raw.get("zoning")
    if z:
        sym = z.get("SYM_CODE", "")
        lay = z.get("LAY_CLASS", "")
        epi = z.get("EPI_NAME", "")
        results["zoning"] = f"{sym} - {lay}".strip(" -") if sym or lay else None
    else:
        results["zoning"] = None

    # Parse height
    h = raw.get("height")
    results["max_height_m"] = _parse_height(h.get("LAY_CLASS") if h else None)

    # Parse FSR
    f = raw.get("fsr")
    results["max_fsr"] = _parse_fsr(f.get("LAY_CLASS") if f else None)

    # Parse lot size
    ls = raw.get("lot_size")
    results["min_lot_size_sqm"] = _parse_lot_size(ls.get("LAY_CLASS") if ls else None)

    # Heritage (local)
    hl = raw.get("heritage_local")
    results["heritage_item"] = hl.get("LAY_CLASS") if hl else None

    # Heritage (state)
    hs = raw.get("heritage_state")
    results["heritage_state"] = hs is not None

    # Bushfire
    bf = raw.get("bushfire")
    results["bushfire_prone"] = bf is not None
    results["bushfire_category"] = bf.get("LAY_CLASS") if bf else None

    # Flood
    fl = raw.get("flood")
    results["flood_planning"] = fl is not None
    results["landslide_risk"] = None

    # Landslide
    ls_risk = raw.get("landslide")
    if ls_risk:
        results["landslide_risk"] = ls_risk.get("LAY_CLASS")

    # Acid sulfate
    ac = raw.get("acid_sulfate")
    results["acid_sulfate_class"] = _parse_acid_sulfate_class(ac.get("LAY_CLASS") if ac else None)

    # Biodiversity
    bio = raw.get("biodiversity")
    results["biodiversity_sensitive"] = bio is not None

    # Drinking water
    dw = raw.get("drinking_water")
    results["drinking_water_catchment"] = dw is not None

    # Wetlands
    wl = raw.get("wetlands")
    results["wetlands_nearby"] = wl is not None

    # Environmentally sensitive
    es = raw.get("env_sensitive")
    results["environmentally_sensitive"] = es.get("LAY_CLASS") if es else None

    # Raw JSON for agent access
    results["raw_json"] = json.dumps(raw, default=str)
    results["queried_at"] = datetime.now(timezone.utc)

    return results


def enrich_pp(session, pp_number: str, lat: float, lng: float) -> None:
    """Query all layers and upsert SiteContext for a PP."""
    from scraper.models import SiteContext

    data = query_all_layers(lat, lng)

    ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()
    if ctx:
        for key, val in data.items():
            setattr(ctx, key, val)
    else:
        ctx = SiteContext(pp_number=pp_number, **data)
        session.add(ctx)
    session.commit()
    logger.info("SiteContext upserted for %s: zoning=%s height=%s flood=%s",
                pp_number, data.get("zoning"), data.get("max_height_m"), data.get("flood_planning"))


def enrich_all_pps(session) -> int:
    """Enrich all PPs that have lat/lng but no SiteContext."""
    from scraper.models import PP, SiteContext

    pps = (
        session.query(PP)
        .filter(PP.latitude.isnot(None), PP.longitude.isnot(None))
        .all()
    )

    enriched = 0
    for pp in pps:
        existing = session.query(SiteContext).filter_by(pp_number=pp.pp_number).first()
        if existing:
            logger.info("Skipping %s — already enriched", pp.pp_number)
            continue
        logger.info("Enriching %s (%.4f, %.4f)", pp.pp_number, pp.latitude, pp.longitude)
        enrich_pp(session, pp.pp_number, pp.latitude, pp.longitude)
        enriched += 1

    return enriched


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Enrich PPs with NSW spatial data")
    parser.add_argument("--pp", type=str, help="Enrich a single PP by number")
    args = parser.parse_args()

    from scraper.models import PP, create_db_engine, create_session

    engine = create_db_engine()
    session = create_session(engine)

    try:
        if args.pp:
            pp = session.get(PP, args.pp)
            if not pp or not pp.latitude:
                print(f"PP {args.pp} not found or has no coordinates")
            else:
                enrich_pp(session, pp.pp_number, pp.latitude, pp.longitude)
                print(f"Enriched {args.pp}")
        else:
            count = enrich_all_pps(session)
            print(f"Enriched {count} PPs")
    finally:
        session.close()
