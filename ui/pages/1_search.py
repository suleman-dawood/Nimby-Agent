"""Page 1: Address search — Find proposals near me."""

import time

import streamlit as st

from pipeline.geocode import geocode_address, find_nearby_pps, find_policy_pps, reverse_geocode_lga
from ui.state import init_session_state, get_db_session

init_session_state()

st.title("What's being proposed near you?")
st.markdown("Enter your NSW address to find planning proposals in your area.")

address = st.text_input(
    "Your address",
    placeholder="e.g. 123 Main Street, Kurnell NSW 2231",
    value=st.session_state.user_address,
)

if st.button("Search", type="primary", use_container_width=True):
    if not address.strip():
        st.warning("Please enter an address.")
    else:
        with st.spinner("Finding your location..."):
            result = geocode_address(address)

        if not result:
            st.error("Could not find that address. Try adding the suburb and postcode.")
        else:
            lat, lng = result
            st.session_state.user_address = address
            st.session_state.user_lat = lat
            st.session_state.user_lng = lng

            session = get_db_session()

            # Find nearby PPs
            with st.spinner("Searching for proposals..."):
                nearby = find_nearby_pps(session, lat, lng, radius_km=10)

                # If nothing within 10km, try 25km
                if not nearby:
                    nearby = find_nearby_pps(session, lat, lng, radius_km=25)

                # Also find policy-level PPs for the user's LGA
                time.sleep(1.1)  # Nominatim rate limit
                lga = reverse_geocode_lga(lat, lng)
                st.session_state.user_lga = lga

                policy = []
                if lga:
                    policy = find_policy_pps(session, lga)
                    # Avoid duplicates
                    nearby_ids = {r["pp_number"] for r in nearby}
                    policy = [p for p in policy if p["pp_number"] not in nearby_ids]

            all_results = nearby + policy
            st.session_state.nearby_pps = all_results

            if all_results:
                st.switch_page("ui/pages/2_results.py")
            else:
                st.info("No planning proposals found near your address. Try a different location.")
