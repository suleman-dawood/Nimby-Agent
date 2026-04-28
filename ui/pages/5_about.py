"""Page 5: About page."""

import streamlit as st

st.title("About Nimby Agent")

st.markdown("""
**Nimby Agent** helps NSW residents understand planning proposals near them.

### What it does
- Scrapes all Planning Proposals currently under exhibition from the
  [NSW Planning Portal](https://www.planningportal.nsw.gov.au/ppr/under%20exhibition)
- Downloads and processes every attached document (planning proposals,
  technical studies, gateway determinations)
- Generates plain-language briefs with verified citations
- Lets you draft evidence-based submissions

### How briefs work
Each brief is auto-generated from the source documents using:
1. **Hybrid retrieval** — vector search + keyword search + reranking
2. **LLM drafting** — Gemini 2.5 Flash writes the brief from retrieved chunks
3. **Citation verification** — every citation is checked against the source page
4. **Fact verification** — numbers, dates, and identifiers are deterministically
   verified against source text (Layer 1) with LLM fallback (Layer 2)
5. **Unsupported claims are removed** — if a fact can't be verified, the sentence
   is stripped from the final brief

### Limitations
- This tool is **not legal or planning advice**
- Briefs are auto-generated and may contain errors despite verification
- Some documents (large maps, scanned images) could not be processed
- Always check the original documents before making decisions
- Exhibition dates and PP status may change — check the portal for current info

### Data
- **23 Planning Proposals** currently under exhibition
- **339 documents** downloaded and processed
- **9,521 text chunks** embedded for retrieval
- Last scraped: April 2026
""")
