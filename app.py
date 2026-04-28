"""Nimby Agent — Planning Proposal Briefs for NSW Residents."""

import streamlit as st

st.set_page_config(
    page_title="Nimby Agent",
    page_icon="🏘",
    layout="wide",
)

pages = [
    st.Page("ui/pages/1_search.py", title="Find Proposals", icon="🔍"),
    st.Page("ui/pages/2_results.py", title="Results", icon="📋"),
    st.Page("ui/pages/3_brief.py", title="Brief", icon="📄"),
    st.Page("ui/pages/4_submission.py", title="Draft Submission", icon="✉"),
    st.Page("ui/pages/5_about.py", title="About", icon="ℹ"),
]

pg = st.navigation(pages)
pg.run()
