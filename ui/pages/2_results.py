"""Page 2: Results list — PPs near the user's address."""

import streamlit as st

from ui.state import init_session_state
from ui.components import pp_card

init_session_state()

if not st.session_state.nearby_pps:
    st.warning("No results. Please search for an address first.")
    if st.button("Go to search"):
        st.switch_page("ui/pages/1_search.py")
    st.stop()

address = st.session_state.user_address
lga = st.session_state.user_lga
results = st.session_state.nearby_pps

st.title(f"Planning proposals near you")
st.caption(f"Showing {len(results)} proposals near {address}")
if lga:
    st.caption(f"Your local government area: {lga}")

for result in results:
    pp_card(result)

st.divider()
if st.button("Search a different address"):
    st.switch_page("ui/pages/1_search.py")
