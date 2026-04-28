"""Search endpoints: geocode + nearby PP discovery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import get_session
from api.schemas.search import (
    GeocodeRequest,
    GeocodeResponse,
    NearbyPP,
    NearbyResponse,
)
from pipeline.geocode import (
    geocode_address,
    reverse_geocode_lga,
    find_nearby_pps,
    find_policy_pps,
    haversine,
)
from scraper.models import PP

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/geocode", response_model=GeocodeResponse)
def geocode(req: GeocodeRequest):
    result = geocode_address(req.address)
    if not result:
        raise HTTPException(status_code=404, detail="Could not geocode address")

    lat, lng = result
    lga = reverse_geocode_lga(lat, lng)

    return GeocodeResponse(
        lat=lat,
        lng=lng,
        lga=lga,
        formatted_address=req.address,
    )


@router.get("/nearby", response_model=NearbyResponse)
def nearby(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(default=10.0, ge=1, le=100),
    session: Session = Depends(get_session),
):
    results = find_nearby_pps(session, lat, lng, radius_km)

    # If too few results, expand radius
    if len(results) < 3 and radius_km < 25:
        results = find_nearby_pps(session, lat, lng, 25.0)

    # Add lat/lng from PP records for map markers
    pp_coords = {}
    for pp in session.query(PP).filter(PP.latitude.isnot(None)).all():
        pp_coords[pp.pp_number] = (pp.latitude, pp.longitude)

    nearby_pps = []
    for r in results:
        coords = pp_coords.get(r["pp_number"])
        r["latitude"] = coords[0] if coords else None
        r["longitude"] = coords[1] if coords else None
        r["exhibition_start"] = str(r["exhibition_start"]) if r["exhibition_start"] else None
        r["exhibition_end"] = str(r["exhibition_end"]) if r["exhibition_end"] else None
        nearby_pps.append(NearbyPP(**r))

    lga = reverse_geocode_lga(lat, lng)
    policy_results = []
    if lga:
        policy = find_policy_pps(session, lga)
        for r in policy:
            if r["pp_number"] not in {p.pp_number for p in nearby_pps}:
                coords = pp_coords.get(r["pp_number"])
                r["latitude"] = coords[0] if coords else None
                r["longitude"] = coords[1] if coords else None
                r["exhibition_start"] = str(r["exhibition_start"]) if r["exhibition_start"] else None
                r["exhibition_end"] = str(r["exhibition_end"]) if r["exhibition_end"] else None
                policy_results.append(NearbyPP(**r))

    return NearbyResponse(results=nearby_pps, lga=lga, policy_results=policy_results)
