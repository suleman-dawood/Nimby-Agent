# Task: Replace Streamlit frontend with Next.js + TypeScript + Mantine + Google Maps

## Goal
Replace the current Python Streamlit UI (`app.py` + `ui/`) with a production-grade
TypeScript frontend. Keep all pipeline logic in Python, expose it via FastAPI,
consume it from a Next.js app.

End state: same 5-page UX the Streamlit app provides, but built on a proper
frontend stack that ships faster, looks better, and supports interactive maps.

## Current state (Streamlit)

    app.py                  # entry point
    ui/
      state.py              # session state management
      components.py         # reusable UI helpers (badges, cards)
      pages/
        1_search.py         # address search → geocode
        2_results.py        # nearby PPs list
        3_brief.py          # brief viewer + citations + Q&A
        4_submission.py     # evidence-based submission generator
        5_about.py          # info + limitations

    All pipeline logic called in-process:
      pipeline.geocode.*    → address → (lat, lng, LGA)
      pipeline.retrieve.*   → hybrid retrieval (Chroma + BM25 + Cohere rerank)
      pipeline.qa.*         → ask question, suggested questions
      pipeline.submission.* → generate evidence-based submission
      pipeline.verify_facts.* → citation fact-checking

    No REST API. No separation between UI and backend.

## Stack

| Layer     | Technology                     | Why                                                    |
|-----------|--------------------------------|--------------------------------------------------------|
| Frontend  | Next.js (App Router)           | SSR for public-interest content, file-based routing    |
| Language  | TypeScript                     | Type safety end-to-end                                 |
| UI kit    | Mantine v7                     | Batteries-included components, good defaults, no Tailwind |
| Maps      | Google Maps + @react-google-maps/api | Places Autocomplete for address input, reliable AU geocoding, familiar UX |
| Data      | TanStack Query                 | Client-side caching, loading/error states              |
| Validation| Zod                            | Runtime validation on form inputs                      |
| Backend   | FastAPI                        | Typed Python API, auto-generates OpenAPI spec          |
| API client| openapi-typescript-codegen     | Generate TS types from FastAPI spec, zero type drift   |

## Deliverables

### Repo structure (additions)

    api/                          # FastAPI backend
      __init__.py
      main.py                     # app factory, CORS, lifespan
      config.py                   # env vars, API keys
      deps.py                     # DB session, pipeline wiring
      routers/
        search.py                 # geocode, discover nearby PPs
        briefs.py                 # get brief, citation lookup
        qa.py                     # ask question, suggested questions
        submissions.py            # generate submission
      schemas/
        search.py                 # request/response models
        briefs.py
        qa.py
        submissions.py

    frontend/                     # Next.js app
      package.json
      tsconfig.json
      next.config.ts
      .env.local                  # NEXT_PUBLIC_GOOGLE_MAPS_KEY, API_URL
      app/
        layout.tsx                # Mantine provider, global layout
        page.tsx                  # Search page (address input + map)
        results/
          page.tsx                # Nearby PP list + map markers
        brief/
          [pp]/page.tsx           # Brief viewer + citations + Q&A
        submission/
          page.tsx                # Concern selector + submission generator
        about/
          page.tsx                # Info + limitations
      components/
        map/
          AddressSearch.tsx        # Google Places Autocomplete input
          ProposalMap.tsx          # Map with PP markers + radius circle
        proposals/
          PPCard.tsx              # Proposal card (distance, days, status)
          PPList.tsx              # Sorted list of PP cards
        brief/
          BriefViewer.tsx         # Markdown renderer with citation buttons
          CitationPanel.tsx       # Sidebar/drawer showing source text
          QAInterface.tsx         # Question input + answer display
        submission/
          ConcernSelector.tsx     # Multi-select concern chips
          SubmissionPreview.tsx   # Generated submission with download
        layout/
          AppShell.tsx            # Mantine AppShell with nav
          Header.tsx
      lib/
        api.ts                    # Generated API client (from OpenAPI spec)
        types.ts                  # Shared frontend types
        hooks/
          useSearch.ts            # TanStack Query hook for search
          useBrief.ts             # TanStack Query hook for brief data
          useQA.ts                # TanStack Query hook for Q&A
          useSubmission.ts        # TanStack Query hook for submissions

## Phase 1: FastAPI backend (api/)

**Input:** existing pipeline functions.
**Output:** REST API that the frontend can call.

### Endpoints

| Method | Path                              | Handler                    | Returns                              |
|--------|-----------------------------------|----------------------------|--------------------------------------|
| POST   | `/api/search/geocode`             | pipeline.geocode           | `{ lat, lng, lga, formatted_address }` |
| GET    | `/api/search/nearby`              | pipeline.geocode.discover  | `[{ pp_number, title, distance_km, days_remaining, ... }]` |
| GET    | `/api/briefs/{pp_number}`         | load brief markdown        | `{ sections: [...], metadata: {...} }` |
| GET    | `/api/briefs/{pp_number}/citation`| chunk lookup by doc+page   | `{ text, document_title, page, pdf_url }` |
| POST   | `/api/qa/ask`                     | pipeline.qa.answer         | `{ answer, citations: [...], verification }` |
| GET    | `/api/qa/{pp_number}/suggestions` | pipeline.qa.suggest        | `[{ question, category }]`          |
| POST   | `/api/submissions/generate`       | pipeline.submission        | `{ markdown, concerns: [...], citations }` |

### Implementation

- Thin wrappers around existing pipeline functions. No logic rewrite.
- Pydantic models for all request/response shapes (in `schemas/`).
- CORS configured for `localhost:3000` (dev) and production domain.
- Single SQLite connection via `deps.py` dependency injection.
- Export OpenAPI JSON at `/openapi.json` for codegen.

### Acceptance test

```bash
# Start API
uvicorn api.main:app --reload --port 8000

# Geocode
curl -X POST localhost:8000/api/search/geocode \
  -H "Content-Type: application/json" \
  -d '{"address": "123 George St, Sydney NSW"}'
# Returns lat, lng, lga

# Nearby PPs
curl "localhost:8000/api/search/nearby?lat=-33.86&lng=151.21&radius_km=10"
# Returns array of PPs with distances

# Brief
curl "localhost:8000/api/briefs/PP-2023-2828"
# Returns parsed brief with sections
```

## Phase 2: Next.js frontend (frontend/)

**Input:** working FastAPI backend.
**Output:** 5-page app matching current Streamlit functionality.

### Page 1: Search (`app/page.tsx`)

- Google Places Autocomplete input field (Mantine TextInput styled, Google autocomplete dropdown)
- On select: geocode via API, store result, show pin on map
- Map shows user location marker
- "Find proposals" button → navigate to `/results`

**Components:** `AddressSearch`, `ProposalMap`

### Page 2: Results (`app/results/page.tsx`)

- Split layout: PP list (left/top) + map (right/bottom)
- Each PP = card with: title, distance, days remaining badge, LGA
- Map shows markers for each PP + radius circle around user address
- Click card or marker → navigate to `/brief/[pp]`
- Sort by distance (default) or exhibition end date

**Components:** `PPCard`, `PPList`, `ProposalMap` (reused with markers)

### Page 3: Brief (`app/brief/[pp]/page.tsx`)

- Brief rendered as styled markdown with Mantine `TypographyStylesProvider`
- Three sections in tabs or accordion: "What's proposed", "What changes", "Things to know"
- Inline citation buttons → open `CitationPanel` drawer with source text excerpt
- Q&A section below: suggested questions as chips, free-text input, answer with citations

**Components:** `BriefViewer`, `CitationPanel`, `QAInterface`

### Page 4: Submission (`app/submission/page.tsx`)

- Concern selector: `Chip.Group` or `MultiSelect` (traffic, heritage, bushfire, etc.)
- Generate button → loading state → rendered submission preview
- Download as markdown button
- Citations shown inline, verifiable

**Components:** `ConcernSelector`, `SubmissionPreview`

### Page 5: About (`app/about/page.tsx`)

- Static content. Mantine `Text`, `List`, `Alert` for limitations/disclaimers.
- No API calls.

### Acceptance test

For each page, verify:
1. Data loads from API (not hardcoded)
2. Loading and error states render correctly
3. Map interactions work (zoom, click markers, autocomplete)
4. Citations open panel with real source text
5. Mobile responsive (Mantine handles most of this)

## Phase 3: Cleanup

- Delete `app.py` and `ui/` directory
- Remove `streamlit` from `pyproject.toml` dependencies
- Add `fastapi`, `uvicorn` to `pyproject.toml`
- Update README with new dev setup instructions

## Implementation order

Build and test sequentially. Each step must work before the next starts.

1. **FastAPI scaffold** — `api/main.py`, CORS, health check endpoint. Verify `uvicorn` starts.
2. **Search endpoints** — wrap `pipeline.geocode` functions. Test with curl.
3. **Brief endpoints** — wrap brief loading + citation lookup. Test with curl.
4. **Q&A + submission endpoints** — wrap remaining pipeline functions. Test with curl.
5. **OpenAPI codegen** — export spec, generate TS client, verify types.
6. **Next.js scaffold** — `create-next-app`, Mantine provider, AppShell layout, routing.
7. **Search page** — Google Places Autocomplete + map. End-to-end test: type address → see pin.
8. **Results page** — fetch nearby PPs, render cards + map markers. Test: search → see results.
9. **Brief page** — fetch brief, render markdown, citation panel, Q&A. Test: click PP → read brief.
10. **Submission page** — concern selector, generate, download. Test: select concerns → get submission.
11. **About page** — static content.
12. **Cleanup** — delete Streamlit code, update deps.

## Dependencies

### Python (additions to pyproject.toml)

    fastapi>=0.115
    uvicorn>=0.32

### Node (frontend/package.json)

    next
    react
    react-dom
    typescript
    @mantine/core
    @mantine/hooks
    @mantine/form
    @react-google-maps/api
    @tanstack/react-query
    zod
    openapi-typescript-codegen   # devDependency

## What NOT to do

- Do not rewrite pipeline logic in TypeScript. Python backend stays.
- Do not add authentication yet. Public-facing read-only app first.
- Do not add WebSocket/SSE for Q&A streaming. Simple request/response first.
- Do not build custom map components. Use library components directly.
- Do not eject from Next.js or customize webpack config.
- Do not write CSS files. Mantine component props + inline styles only.
- Do not add i18n, analytics, or monitoring in the first pass.
- Do not deploy until all 5 pages work locally end-to-end.

## Start here

1. Create `api/main.py` with FastAPI app + health endpoint (10 mins).
2. Add search router wrapping geocode pipeline (30 mins).
3. Test geocode + nearby endpoints with curl (10 mins).
4. Scaffold Next.js app with Mantine + Google Maps (30 mins).
5. Build search page with Places Autocomplete (1 evening).
6. Build results page with map markers (1 evening).
7. Build brief page with citations (1 evening).
8. Build submission page (1 evening).
9. End-to-end test: address → results → brief → submission.
10. Delete Streamlit.
