"""Session state management for the Streamlit app."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from scraper.models import create_db_engine, create_session


@st.cache_resource
def get_engine():
    return create_db_engine()


def get_db_session() -> Session:
    return create_session(get_engine())


def init_session_state():
    defaults = {
        "user_address": "",
        "user_lat": None,
        "user_lng": None,
        "user_lga": None,
        "nearby_pps": [],
        "selected_pp": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
