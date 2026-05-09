"""Site context endpoints — NSW planning controls, hazards, environmental data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import get_session
from api.schemas.site_context import SiteContextResponse
from scraper.models import SiteContext

router = APIRouter(prefix="/api/site-context", tags=["site-context"])


def _to_response(ctx: SiteContext) -> SiteContextResponse:
    return SiteContextResponse(
        pp_number=ctx.pp_number,
        zoning=ctx.zoning,
        max_height_m=ctx.max_height_m,
        max_fsr=ctx.max_fsr,
        min_lot_size_sqm=ctx.min_lot_size_sqm,
        heritage_item=ctx.heritage_item,
        heritage_state=ctx.heritage_state or False,
        bushfire_prone=ctx.bushfire_prone or False,
        bushfire_category=ctx.bushfire_category,
        flood_planning=ctx.flood_planning or False,
        landslide_risk=ctx.landslide_risk,
        acid_sulfate_class=ctx.acid_sulfate_class,
        biodiversity_sensitive=ctx.biodiversity_sensitive or False,
        drinking_water_catchment=ctx.drinking_water_catchment or False,
        wetlands_nearby=ctx.wetlands_nearby or False,
        environmentally_sensitive=ctx.environmentally_sensitive,
        queried_at=ctx.queried_at,
    )


@router.get("/{pp_number}", response_model=SiteContextResponse)
def get_site_context(pp_number: str, session: Session = Depends(get_session)):
    """Get cached spatial data for a proposal."""
    ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()
    if not ctx:
        raise HTTPException(404, "No site context for this proposal")
    return _to_response(ctx)


@router.get("/query/live", response_model=SiteContextResponse)
def query_live(
    lat: float = Query(...),
    lng: float = Query(...),
    session: Session = Depends(get_session),
):
    """Live query NSW spatial data for any lat/lng. Not cached."""
    from pipeline.spatial import query_all_layers

    data = query_all_layers(lat, lng)
    return SiteContextResponse(
        pp_number="query",
        zoning=data.get("zoning"),
        max_height_m=data.get("max_height_m"),
        max_fsr=data.get("max_fsr"),
        min_lot_size_sqm=data.get("min_lot_size_sqm"),
        heritage_item=data.get("heritage_item"),
        heritage_state=data.get("heritage_state", False),
        bushfire_prone=data.get("bushfire_prone", False),
        bushfire_category=data.get("bushfire_category"),
        flood_planning=data.get("flood_planning", False),
        landslide_risk=data.get("landslide_risk"),
        acid_sulfate_class=data.get("acid_sulfate_class"),
        biodiversity_sensitive=data.get("biodiversity_sensitive", False),
        drinking_water_catchment=data.get("drinking_water_catchment", False),
        wetlands_nearby=data.get("wetlands_nearby", False),
        environmentally_sensitive=data.get("environmentally_sensitive"),
        queried_at=data.get("queried_at"),
    )
