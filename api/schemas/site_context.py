"""Site context schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SiteContextResponse(BaseModel):
    pp_number: str
    zoning: str | None
    max_height_m: float | None
    max_fsr: float | None
    min_lot_size_sqm: float | None
    heritage_item: str | None
    heritage_state: bool
    bushfire_prone: bool
    bushfire_category: str | None
    flood_planning: bool
    landslide_risk: str | None
    acid_sulfate_class: int | None
    biodiversity_sensitive: bool
    drinking_water_catchment: bool
    wetlands_nearby: bool
    environmentally_sensitive: str | None
    queried_at: datetime | None
