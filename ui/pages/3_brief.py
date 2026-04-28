"""Page 3: Brief viewer with clickable citations."""

import os
import re
import hashlib

import streamlit as st

from scraper.models import Document
from pipeline.llm_utils import CITE_PATTERN, find_chunk
from ui.state import init_session_state, get_db_session

init_session_state()

pp_number = st.session_state.selected_pp

if not pp_number:
    st.warning("No proposal selected. Please search first.")
    if st.button("Go to search"):
        st.switch_page("ui/pages/1_search.py")
    st.stop()

brief_path = f"data/briefs/{pp_number}.md"

if not os.path.exists(brief_path):
    st.warning(f"Brief for {pp_number} has not been generated yet.")
    st.stop()

brief_text = open(brief_path).read()

# Init citation viewer state
if "citation_text" not in st.session_state:
    st.session_state.citation_text = None
    st.session_state.citation_doc = None
    st.session_state.citation_page = None
    st.session_state.citation_url = None


def show_citation(doc_title: str, page: int):
    """Load citation source into session state."""
    session = get_db_session()
    chunk = find_chunk(session, pp_number, doc_title, page)
    doc = session.query(Document).filter(
        Document.pp_number == pp_number,
        Document.title.like(f"%{doc_title[:30]}%"),
    ).first()

    st.session_state.citation_text = chunk.text[:1500] if chunk else "Source chunk not found in database."
    st.session_state.citation_doc = doc_title
    st.session_state.citation_page = page
    st.session_state.citation_url = doc.url if doc else None


# Sidebar: citation viewer
with st.sidebar:
    st.header("Source viewer")
    if st.session_state.citation_text:
        st.markdown(f"**{st.session_state.citation_doc}**")
        st.markdown(f"Page {st.session_state.citation_page}")
        st.divider()
        st.text(st.session_state.citation_text)
        if st.session_state.citation_url:
            st.link_button("Open source PDF", st.session_state.citation_url)
        if st.button("Clear"):
            st.session_state.citation_text = None
            st.rerun()
    else:
        st.caption("Click a citation below to view the source text.")

# Parse brief into sections
sections = re.split(r'^(## .+)$', brief_text, flags=re.MULTILINE)

# Collect all unique citations with stable keys
all_citations = []
for match in CITE_PATTERN.finditer(brief_text):
    doc_title = match.group(1).strip()
    page = int(match.group(2))
    key = f"{doc_title}|{page}"
    if key not in {c["key"] for c in all_citations}:
        all_citations.append({"doc_title": doc_title, "page": page, "key": key})

# Render sections
for part in sections:
    if not part.strip():
        continue

    if part.startswith("## References"):
        with st.expander("References", expanded=False):
            # Strip the heading, render just the list
            ref_body = part.replace("## References", "").strip()
            st.markdown(ref_body)
        continue

    if part.startswith("---"):
        st.caption(part.strip("- \n*"))
        continue

    if part.startswith("## "):
        st.markdown(part)
        continue

    if part.startswith("# ") or part.startswith("**PP") or part.startswith("**Council") or part.startswith("**Exhibition") or part.startswith("**Type") or part.startswith("**Address"):
        st.markdown(part)
        continue

    # Section body: find citations in this part
    section_cites = list(CITE_PATTERN.finditer(part))

    # Clean text for display (remove citation markers)
    clean = CITE_PATTERN.sub("", part).strip()
    clean = re.sub(r'\s{2,}', ' ', clean)
    if clean:
        st.markdown(clean)

    # Citation buttons with stable keys
    if section_cites:
        seen = set()
        # Use hash of section content for stable key prefix
        section_hash = hashlib.md5(part[:100].encode()).hexdigest()[:8]

        button_cols = st.columns(min(4, len(section_cites)))
        col_idx = 0
        for match in section_cites:
            doc_title = match.group(1).strip()
            page = int(match.group(2))
            cite_key = f"{doc_title}|{page}"
            if cite_key in seen:
                continue
            seen.add(cite_key)

            label = f"{doc_title[:28]}... p.{page}" if len(doc_title) > 28 else f"{doc_title} p.{page}"
            btn_key = f"c_{section_hash}_{page}_{col_idx}"

            with button_cols[col_idx % len(button_cols)]:
                if st.button(f"📄 {label}", key=btn_key):
                    show_citation(doc_title, page)
                    st.rerun()
            col_idx += 1

# Q&A section
st.divider()
st.subheader("Ask a question about this proposal")

# Suggested questions
from pipeline.qa import get_suggested_questions, answer_question
session = get_db_session()
suggestions = get_suggested_questions(pp_number, session)

if suggestions:
    cols = st.columns(min(3, len(suggestions)))
    for i, q in enumerate(suggestions):
        with cols[i % len(cols)]:
            if st.button(q, key=f"sq_{i}"):
                st.session_state.qa_question = q

qa_input = st.text_input(
    "Or type your own question",
    value=st.session_state.get("qa_question", ""),
    key="qa_input",
)

if st.button("Ask", disabled=not qa_input):
    import os
    os.environ.setdefault("GOOGLE_API_KEY", open(".env").read().split("GOOGLE_API_KEY=")[1].split("\n")[0])
    os.environ.setdefault("COHERE_API_KEY", open(".env").read().split("COHERE_API_KEY=")[1].split("\n")[0])

    with st.spinner("Finding the answer..."):
        result = answer_question(pp_number, qa_input)

    st.markdown("---")
    # Clean citation markers for display, show as footnotes
    display = CITE_PATTERN.sub("", result.answer).strip()
    st.markdown(display)

    if result.citations:
        with st.expander(f"Sources ({len(result.citations)} citations)"):
            seen = set()
            for c in result.citations:
                key = (c["document_title"], c["page"])
                if key not in seen:
                    seen.add(key)
                    st.caption(f"{c['document_title']}, p.{c['page']}")

    stats = result.verification_stats
    if stats.get("total"):
        st.caption(f"Facts verified: {stats['verified']}/{stats['total']}")

# Action buttons
st.divider()
col1, col2 = st.columns(2)
with col1:
    if st.button("Draft a submission", type="primary", use_container_width=True):
        st.switch_page("ui/pages/4_submission.py")
with col2:
    if st.button("Search another address", use_container_width=True):
        st.switch_page("ui/pages/1_search.py")
