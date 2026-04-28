"""Reusable UI components."""

from __future__ import annotations

from datetime import date

import streamlit as st


def days_badge(exhibition_end: date | None) -> str:
    """Return a colored badge string for days remaining."""
    if not exhibition_end:
        return ":gray[Unknown]"
    remaining = (exhibition_end - date.today()).days
    if remaining < 0:
        return ":gray[Closed]"
    elif remaining <= 7:
        return f":red[{remaining} days left]"
    elif remaining <= 14:
        return f":orange[{remaining} days left]"
    else:
        return f":green[{remaining} days left]"


def distance_label(distance_km: float, geo_source: str) -> str:
    """Format distance for display."""
    if geo_source == "lga_policy":
        return "Affects your LGA"
    if distance_km < 0.1:
        return "At your location"
    return f"{distance_km:.1f} km away"


def pp_card(result: dict):
    """Render a PP result as a card."""
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{result['title']}**")
            st.caption(f"{result.get('council') or 'Council not specified'}")
        with col2:
            st.markdown(days_badge(result.get("exhibition_end")))
            st.caption(distance_label(result["distance_km"], result.get("geo_source", "")))

        if st.button("View brief", key=f"view_{result['pp_number']}"):
            st.session_state.selected_pp = result["pp_number"]
            st.switch_page("ui/pages/3_brief.py")
