# NSW Planning Proposals Scraper

Scrapes all Planning Proposals currently under exhibition from the
[NSW Planning Portal](https://www.planningportal.nsw.gov.au/ppr/under%20exhibition),
downloads every attached document, and stores everything in a local dataset
with a SQLite manifest.

No parsing of PDF contents, no LLM work, no classification — just raw data
capture for downstream pipeline use.

## Quick start

```bash
uv sync
uv run python -m scraper.run
```

## Limited test run

```bash
uv run python -m scraper.run --limit 3
```

## Outputs

```
data/
  raw_html/          # One HTML file per PP detail page, plus _index.html
    _index.html
    PP-2024-450.html
    ...
  documents/         # Deduplicated PDFs, named by SHA-256
    a1b2c3d4....pdf
manifest.sqlite      # Metadata + document tracking
```

## Inspecting the manifest

```bash
sqlite3 manifest.sqlite

-- Count PPs and documents
SELECT COUNT(*) FROM pps;
SELECT COUNT(*) FROM documents;

-- Show download failures
SELECT pp_number, url, download_status
FROM documents
WHERE download_status NOT IN ('ok', 'pending');

-- Total download size
SELECT printf('%.1f MB', SUM(byte_size) / 1048576.0)
FROM documents WHERE download_status = 'ok';
```

## Known limitations

- Two detail page templates are detected (council-led "Template A" and
  State-led "Template B"). Other layouts log an error and produce an empty
  document list — the HTML is still saved for manual inspection.
- Serial execution only. First full run takes 30–60 minutes.
- Re-runs are idempotent: pages are re-scraped but already-downloaded
  documents are skipped.

## Polite scraping

The default User-Agent is a placeholder. Update it in `scraper/fetch.py`
before heavy use:

```python
USER_AGENT = "nsw-ppr-scraper/0.1 (+github.com/your-username/your-repo)"
```

Requests are throttled to 1.5s between calls with exponential backoff on
server errors.

## Running parse tests

After a first scrape, copy fixture files for the parser smoke tests:

```bash
cp data/raw_html/PP-2024-450.html scraper/fixtures/
cp data/raw_html/PP-2023-2828.html scraper/fixtures/
uv run python -m scraper.test_parse
```
