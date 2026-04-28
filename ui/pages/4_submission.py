"""Page 4: Submission drafter."""

import streamlit as st

from ui.state import init_session_state

init_session_state()

pp_number = st.session_state.selected_pp

if not pp_number:
    st.warning("No proposal selected. Please search and select a proposal first.")
    if st.button("Go to search"):
        st.switch_page("ui/pages/1_search.py")
    st.stop()

st.title(f"Draft a submission")
st.caption(f"For planning proposal {pp_number}")

CONCERNS = [
    "Traffic and transport",
    "Environmental impact",
    "Density and scale",
    "Heritage",
    "Bushfire risk",
    "Noise and acoustic",
    "Neighbourhood character",
    "Infrastructure capacity",
    "Parking",
    "Construction impact",
    "Aircraft noise",
    "Contamination",
]

selected = st.multiselect("Select your concerns", CONCERNS)
free_text = st.text_area("Additional concerns (optional)", placeholder="Describe any specific concerns...")
user_name = st.text_input("Your name (optional)", value="A Concerned Resident")
user_address = st.text_input("Your address (optional)", value=st.session_state.get("user_address", ""))

if st.button("Generate submission", type="primary", disabled=not selected, use_container_width=True):
    import os
    os.environ.setdefault("GOOGLE_API_KEY", open(".env").read().split("GOOGLE_API_KEY=")[1].split("\n")[0])
    os.environ.setdefault("COHERE_API_KEY", open(".env").read().split("COHERE_API_KEY=")[1].split("\n")[0])

    from pipeline.submission import generate_submission

    with st.spinner("Generating your submission... This may take a minute."):
        result = generate_submission(
            pp_number=pp_number,
            concerns=selected,
            free_text=free_text,
            user_name=user_name,
            user_address=user_address,
        )

    st.markdown("---")
    st.markdown(result.markdown)

    if result.dropped_concerns:
        st.warning("Some concerns could not be included due to lack of supporting evidence.")

    stats = result.citation_stats
    st.caption(f"Citations: {stats.get('verified', 0)}/{stats.get('total', 0)} verified")

    # Download
    st.download_button(
        "Download as text",
        data=result.markdown,
        file_name=f"submission_{pp_number}.md",
        mime="text/markdown",
    )

st.divider()
if st.button("Back to brief"):
    st.switch_page("ui/pages/3_brief.py")
