"""Geocoding and PP discovery by location."""

from __future__ import annotations

import json
import logging
import math
import time

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from sqlalchemy.orm import Session

from scraper.models import PP
from scraper import repository

logger = logging.getLogger(__name__)

_geocoder = Nominatim(user_agent="nimby-agent/0.1", timeout=10)


def geocode_address(address: str) -> tuple[float, float] | None:
    """Geocode a street address to (lat, lng). Biased to NSW Australia."""
    query = f"{address}, NSW, Australia"
    try:
        location = _geocoder.geocode(query, exactly_one=True)
        if location:
            return (location.latitude, location.longitude)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocode failed for '%s': %s", address, e)
    return None


def reverse_geocode_lga(lat: float, lng: float) -> str | None:
    """Reverse geocode to get the LGA/council name for a lat/lng."""
    try:
        location = _geocoder.reverse((lat, lng), exactly_one=True)
        if location and location.raw:
            addr = location.raw.get("address", {})
            return (
                addr.get("city")
                or addr.get("municipality")
                or addr.get("county")
                or addr.get("town")
            )
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Reverse geocode failed: %s", e)
    return None


def geocode_pp(session: Session, pp: PP) -> tuple[float, float, str] | None:
    """Geocode a PP. Returns (lat, lng, source) or None.

    Strategy:
    1. Try first address from pp.addresses JSON array
    2. Fall back to council/LGA centroid
    """
    # Try addresses
    if pp.addresses:
        try:
            addresses = json.loads(pp.addresses)
            if isinstance(addresses, list) and addresses:
                for addr in addresses:
                    if not addr or len(addr) < 5:
                        continue
                    result = geocode_address(addr)
                    if result:
                        return (result[0], result[1], "address")
                    time.sleep(1.1)  # Nominatim rate limit
        except (json.JSONDecodeError, TypeError):
            pass

    # Fall back to council LGA centroid
    council = pp.council
    if council:
        result = geocode_address(f"{council} Council, NSW")
        if result:
            return (result[0], result[1], "lga_centroid")
        time.sleep(1.1)

    return None


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearby_pps(session: Session, lat: float, lng: float, radius_km: float = 10.0) -> list[dict]:
    """Find all PPs within radius_km of a point, sorted by distance."""
    pps = repository.get_pps_with_geocode(session)
    results = []

    for pp in pps:
        dist = haversine(lat, lng, pp.latitude, pp.longitude)
        if dist <= radius_km:
            results.append({
                "pp_number": pp.pp_number,
                "title": pp.title,
                "council": pp.council,
                "distance_km": round(dist, 1),
                "exhibition_start": pp.exhibition_start,
                "exhibition_end": pp.exhibition_end,
                "stage": pp.stage,
                "geo_source": pp.geo_source,
                "description": pp.description,
            })

    return sorted(results, key=lambda r: r["distance_km"])


def find_policy_pps(session: Session, lga_name: str) -> list[dict]:
    """Find PPs that affect a whole LGA (policy-level, matched by council name)."""
    pps = repository.get_pps_for_lga(session, lga_name)
    results = []

    for pp in pps:
        if pp.geo_source == "lga_centroid":
            results.append({
                "pp_number": pp.pp_number,
                "title": pp.title,
                "council": pp.council,
                "distance_km": 0,
                "exhibition_start": pp.exhibition_start,
                "exhibition_end": pp.exhibition_end,
                "stage": pp.stage,
                "geo_source": "lga_policy",
                "description": pp.description,
            })

    return results
