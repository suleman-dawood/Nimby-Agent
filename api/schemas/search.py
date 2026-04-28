"""Request/response models for search endpoints."""

from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    address: str = Field(..., min_length=3, description="Street address to geocode")


class GeocodeResponse(BaseModel):
    lat: float
    lng: float
    lga: str | None = None
    formatted_address: str


class NearbyPP(BaseModel):
    pp_number: str
    title: str | None
    council: str | None
    distance_km: float
    exhibition_start: str | None
    exhibition_end: str | None
    stage: str | None
    geo_source: str | None
    description: str | None
    latitude: float | None = None
    longitude: float | None = None


class NearbyResponse(BaseModel):
    results: list[NearbyPP]
    lga: str | None = None
    policy_results: list[NearbyPP] = []
