# Nimby Agent

AI-powered planning proposal analysis tool for NSW residents. Enter an address, find nearby planning proposals, get plain-language briefs with grounded citations, ask questions, and generate evidence-based submissions.

## Stack

Scraper:  Python, Playwright, SQLite manifest
Pipeline: PDF extraction, document classification, ChromaDB + BM25 + Cohere rerank (hybrid retrieval), LLM brief generation with citation verification
Backend: FastAPI, Python
Frontend: Next.js (App Router), TypeScript, Mantine UI, Google Maps

## How it works

1. **Scrape** — Crawls the [NSW Planning Portal](https://www.planningportal.nsw.gov.au/ppr/under%20exhibition) for all proposals under exhibition. Downloads every attached PDF. Stores metadata in SQLite.
2. **Extract & classify** — Extracts text from PDFs page by page, classifies documents by tier and concern tag.
3. **Embed** — Chunks text and stores embeddings in ChromaDB for semantic search.
4. **Search** — User enters an address. Geocoded via Google Maps, matched to nearby planning proposals.
5. **Brief** — Generates a plain-language brief per proposal. Every factual claim cites a specific document and page. Citations resolve to real extracted text.
6. **Q&A** — Ask questions about any proposal. Hybrid retrieval (vector + BM25 + rerank) finds relevant chunks, LLM answers with grounded citations.
7. **Submission** — Generates evidence-based submissions using verified claims from the proposal documents.

## Project structure

```
scraper/          # Portal crawler + PDF downloader
pipeline/         # classify, extract, embed, retrieve, brief, qa, submission
api/              # FastAPI backend
frontend/         # Next.js + Mantine + Google Maps
data/             # Raw HTML, downloaded PDFs, ChromaDB store
plans/            # Build plans per component
tests/            # Unit + integration tests
```

## Quick start

### Scraper

```bash
uv sync
uv run python -m scraper.run          # full scrape
uv run python -m scraper.run --limit 3 # limited test run
```

### Backend

```bash
uvicorn api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
