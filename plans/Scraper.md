# Task: Scrape all Planning Proposals currently on exhibition from NSW Planning Portal

## Goal
Download all ~60 Planning Proposals currently under exhibition, plus every
document attached to each, as a static local dataset. No parsing, no LLM
work, no classification. Just: HTML + PDFs + a manifest mapping them together.

Output is reproducible raw data that downstream pipeline work can depend on.

## Source
Index page: https://www.planningportal.nsw.gov.au/ppr/under%20exhibition

Each PP has a detail page at /ppr/under-exhibition/<slug> containing:
- Metadata (PP number, address, council, exhibition dates, etc.)
- A list of documents, each with a title, category label, and URL

Document URLs look like:
  https://apps.planningportal.nsw.gov.au/prweb/PRRestService/DocMgmt/v1/PublicDocuments/<token>
and return PDFs when fetched directly.

## Deliverables

A repo structure:

    scraper/
      __init__.py
      fetch.py          # HTTP layer (retries, backoff, polite delays)
      index.py          # parse the index page to get all PP URLs
      detail.py         # parse a PP detail page to extract metadata + doc list
      download.py       # download + hash + store PDFs
      run.py            # orchestrates: one pass, serial, end to end
    data/
      raw_html/
        <pp_number>.html
      documents/
        <sha256>.pdf
    manifest.sqlite
    pyproject.toml
    README.md

## Manifest schema (SQLite)

Two tables:

    CREATE TABLE pps (
      pp_number TEXT PRIMARY KEY,
      slug TEXT NOT NULL,
      detail_url TEXT NOT NULL,
      title TEXT,
      council TEXT,
      addresses TEXT,              -- JSON array of address strings
      description TEXT,
      exhibition_start DATE,
      exhibition_end DATE,
      stage TEXT,
      relevant_planning_authority TEXT,
      raw_html_path TEXT NOT NULL,
      scraped_at TIMESTAMP NOT NULL
    );

    CREATE TABLE documents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      pp_number TEXT NOT NULL REFERENCES pps(pp_number),
      title TEXT NOT NULL,
      category TEXT,               -- portal's label, e.g. "Proposal for Public Exhibition"
      url TEXT NOT NULL,
      sha256 TEXT,                 -- null if download failed
      file_path TEXT,              -- data/documents/<sha256>.pdf
      content_type TEXT,
      byte_size INTEGER,
      download_status TEXT NOT NULL,  -- 'ok' | 'failed_<reason>' | 'skipped_duplicate_url'
      scraped_at TIMESTAMP NOT NULL,
      UNIQUE(pp_number, url)
    );

    CREATE INDEX idx_docs_sha ON documents(sha256);
    CREATE INDEX idx_docs_pp ON documents(pp_number);

## Implementation requirements

**HTTP layer (fetch.py):**
- Use httpx with a single Client for connection pooling.
- User-Agent: "nsw-ppr-scraper/0.1 (+github.com/<placeholder>)". Leave the
  placeholder in the code and note in README that the user should change it.
- Timeout: 30s per request.
- Retry on 429, 500, 502, 503, 504 with exponential backoff: 2s, 4s, 8s, max 3 retries.
- Don't retry on 4xx other than 429.
- time.sleep(1.5) between requests to the same host.
- Log every request: URL, status, elapsed time.

**Index parsing (index.py):**
- Fetch https://www.planningportal.nsw.gov.au/ppr/under%20exhibition.
- Note: the portal may paginate. Check for pagination links and follow them
  until no "next" page exists.
- From each page, extract every PP tile's detail URL.
- Also extract the visible PP number and title if present on the tile (useful
  for the manifest even before the detail page is fetched).
- Return a list of dicts: [{pp_number, title, detail_url}, ...]
- Save the raw index HTML to data/raw_html/_index.html for debugging.

**Detail parsing (detail.py):**
- Given a detail_url, fetch the HTML and save it to data/raw_html/<pp_number>.html.
- Parse with BeautifulSoup.
- Extract:
  - pp_number (from the "Number" field in Activity Details, or the URL slug as fallback)
  - title (the page h1)
  - council / local_government_area
  - description (the main prose block under the title)
  - addresses (list; one PP can have multiple addresses as in Dural)
  - exhibition_start, exhibition_end (parse as ISO dates from the DD/MM/YYYY format)
  - stage, relevant_planning_authority (from Activity Details)
  - documents: list of {title, category, url} for every document listed

**IMPORTANT: the portal has at least two page templates.**
- Template A (council-led, most common): has a "Documents (N)" section with
  individual document entries. Each entry has a category label, a title,
  and a "View" link.
- Template B (State-led rezonings like Kurnell, PP-2023-2828): has grouped
  sections like "Exhibition Documents" and "Technical Studies" instead.
  Document names may not be prefixed with the PP number.

Implement both. Detect template by checking for the presence of specific
structural markers. If neither template matches, log an error with the
pp_number and save the HTML but produce an empty document list. Do not
crash the whole run.

**Downloading (download.py):**
- For each document URL in the manifest:
  - Skip if this pp_number + url combination already has download_status='ok'
    in the manifest (idempotent re-runs).
  - Fetch bytes, compute SHA-256.
  - If data/documents/<sha256>.pdf already exists, don't re-write it
    (deduplication across PPs that share documents).
  - Otherwise write it.
  - Update manifest with sha256, file_path, content_type, byte_size, download_status.
  - On failure, set download_status='failed_<http_status_or_exception>' and
    continue. Don't crash the run.
- Validate the downloaded bytes are actually a PDF (starts with '%PDF-'). If
  not, set download_status='failed_not_pdf' and don't store the file.

**Orchestration (run.py):**
- Argument parser with a single flag: --limit N (process only N PPs, useful
  for testing).
- Steps:
  1. Ensure data/ directories and manifest.sqlite exist.
  2. Fetch index, get list of PP URLs.
  3. For each PP (respect --limit):
     - Upsert pps row (so we have a record even if detail parsing fails).
     - Fetch + parse detail page.
     - Update pps row with full metadata.
     - For each document, upsert documents row.
     - Download all documents for this PP.
  4. Print a summary at the end: N PPs processed, M documents downloaded,
     K failures (grouped by reason), total bytes on disk.

- Progress: use tqdm for the outer PP loop and an inline print for documents
  within each PP.

- The whole run is serial. No concurrency. No async. Accept that it will take
  30-60 minutes on first run. Concurrency is a later optimization; correctness
  comes first.

## Dependencies

Use uv. pyproject.toml should declare:

    httpx>=0.27
    beautifulsoup4>=4.12
    lxml>=5.0                # faster parser for bs4
    tqdm>=4.66
    python-dateutil>=2.9     # lenient date parsing

Python 3.11+.

## README.md

Document:
- What this scrapes and why
- How to run: `uv sync && uv run python -m scraper.run`
- How to run a limited test: `uv run python -m scraper.run --limit 3`
- Where outputs go
- Known limitations (two templates detected so far, others logged as errors)
- Polite-scraping note: the User-Agent placeholder should be updated before
  heavy use
- How to inspect the manifest: `sqlite3 manifest.sqlite` with a couple of
  example queries

## What NOT to do

- Do not parse PDF contents. That's a later pipeline step.
- Do not classify documents by tier. That's a later step.
- Do not use any LLM calls. This script is pure scraping + storage.
- Do not add concurrency, async, or worker pools on the first pass.
- Do not add CLI flags beyond --limit. Keep it simple.
- Do not try to handle authentication. The portal is public.
- Do not follow links within PDFs or do any recursive fetching beyond the
  listed documents.
- Do not fail the whole run on any single PP's error. Log and continue.

## Acceptance criteria

After `uv run python -m scraper.run` completes on a fresh checkout:

1. `data/raw_html/` contains one file per PP discovered on the index, plus _index.html.
2. `data/documents/` contains deduplicated PDFs, named by SHA-256.
3. `manifest.sqlite` has:
   - One row in `pps` for every PP from the index
   - Rows in `documents` for every document link found on every detail page
   - `download_status` populated for every document row
4. `uv run python -m scraper.run` a second time should be a near no-op
   (idempotent; only re-scrapes pages, skips already-downloaded documents).
5. A closing summary prints counts and any failures.
6. Running with `--limit 3` processes only 3 PPs end to end.

## Testing approach

Don't write a test suite. This is a scraper; the real test is running it and
inspecting outputs. But do add:

- A `scraper/test_parse.py` that loads a couple of checked-in sample HTML
  files (save one Dural-style and one Kurnell-style response under
  `scraper/fixtures/`) and asserts the detail parser returns expected
  fields. Run with `uv run python -m scraper.test_parse`.

Capture the fixtures by running the scraper once and copying
data/raw_html/PP-2024-450.html and PP-2023-2828.html into fixtures/.

## Start here

1. Create the repo skeleton (pyproject.toml, directories, empty files).
2. Implement fetch.py first, with a smoke test that fetches the index page.
3. Implement index.py, print the discovered PP URLs, confirm count ≈ 60.
4. Implement detail.py against one PP (Dural: PP-2024-450).
5. Implement detail.py against Kurnell (PP-2023-2828) to handle Template B.
6. Implement download.py on a single PP's documents.
7. Wire up run.py.
8. Run end-to-end with --limit 3.
9. Run end-to-end without limit.
10. Write README, commit.