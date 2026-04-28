# Task: Classify documents, extract text, embed chunks, and generate PP briefs

## Goal
Turn the raw scraper output (339 PDFs across 23 PPs) into a pipeline that:
1. Classifies each document by tier and concern
2. Extracts text from PDFs into searchable chunks
3. Embeds chunks for semantic retrieval
4. Generates plain-language briefs per PP with grounded citations

End state: for any PP, produce a markdown brief where every factual claim
cites a specific document and page, and that citation resolves to real text.

## Current state (scraper output)

    manifest.sqlite:
      23 PPs in `pps` table (all fields populated)
      344 documents in `documents` table (339 downloaded OK, 5 failed_not_pdf)
      5.07 GB of PDFs in data/documents/

    Key data points from audit:
      - 34 portal categories already in `documents.category`
      - 317 distinct document titles (mostly unique)
      - PP sizes range from 0.5 MB / 2 docs (Shellharbour) to 2.5 GB / 37 docs (Kurnell)
      - 1 PP has zero docs (PP-2025-1092) — portal has none
      - Portal categories are the strongest signal for classification

## Deliverables

### Repo structure (additions to existing)

    pipeline/
      __init__.py
      classify.py        # tier + concern classification using portal categories
      extract.py         # PDF text extraction with pdfplumber, page-level chunks
      embed.py           # chunk embedding + vector store (ChromaDB)
      retrieve.py        # retrieval function: (pp_number, query, k) -> chunks
      brief.py           # LangGraph brief generator pipeline
      run_pipeline.py    # orchestrates steps 1-4 in order
    data/
      chroma/            # ChromaDB persistent store

### Schema additions (manifest.sqlite)

    ALTER TABLE documents ADD COLUMN tier INTEGER;
    ALTER TABLE documents ADD COLUMN concern_tag TEXT;

    CREATE TABLE chunks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      document_id INTEGER NOT NULL REFERENCES documents(id),
      pp_number TEXT NOT NULL,
      page_number INTEGER NOT NULL,
      chunk_index INTEGER NOT NULL,
      text TEXT NOT NULL,
      char_count INTEGER NOT NULL,
      extraction_method TEXT NOT NULL,  -- 'pdfplumber' | 'ocr' | 'failed'
      created_at TIMESTAMP NOT NULL,
      UNIQUE(document_id, page_number, chunk_index)
    );

    CREATE INDEX idx_chunks_doc ON chunks(document_id);
    CREATE INDEX idx_chunks_pp ON chunks(pp_number);

    CREATE TABLE briefs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      pp_number TEXT NOT NULL REFERENCES pps(pp_number),
      version INTEGER NOT NULL DEFAULT 1,
      markdown TEXT NOT NULL,
      citations_json TEXT NOT NULL,   -- JSON array of {claim, document_id, page, chunk_id, verified}
      generated_at TIMESTAMP NOT NULL,
      UNIQUE(pp_number, version)
    );

## Step 1: Document classifier (classify.py)

**Input:** `documents` table with `category` and `title` columns.
**Output:** `tier` (1/2/3) and `concern_tag` populated for all 344 rows.

### Tier definitions

| Tier | What                          | Portal categories                                                    | Expected count |
|------|-------------------------------|----------------------------------------------------------------------|----------------|
| 1    | The actual planning proposal  | "Proposal for Public Exhibition", "Draft Planning Proposal",         | ~25-50 docs    |
|      |                               | "Planning Proposal for agency consultation",                         |                |
|      |                               | "Planning Proposal post exhibition - revised",                       |                |
|      |                               | "Exhibition Documents" (Template B)                                  |                |
| 2    | Technical studies / evidence  | "Acoustic report", "Traffic report", "Heritage Impact Assessment",   | ~80-120 docs   |
|      |                               | "Flora and Fauna Report", "Contamination and/or remediation...",     |                |
|      |                               | "Aboriginal Cultural Heritage Assessment Report",                    |                |
|      |                               | "Flood risk management report", "Bushfire report",                   |                |
|      |                               | "Urban design and built form assessment",                            |                |
|      |                               | "Infrastructure assessment", "Technical Studies",                    |                |
|      |                               | "Retail assessment", "Draft Development Control Plan",               |                |
|      |                               | "Coastal Design Guidelines..."                                       |                |
| 3    | Admin / process documents     | "Gateway determination", "Gateway determination report",             | rest           |
|      |                               | "Gateway letter to council", "Council report and resolution",        |                |
|      |                               | "Gateway Alteration document", "Record of decision",                 |                |
|      |                               | "Completed declaration form RR", "Owner's consent",                  |                |
|      |                               | "Planning Proposal maps", "Map of the applicable land area",         |                |
|      |                               | "Plans"                                                              |                |

### Concern tags

Derived from category + title keywords. Possible values:
`traffic`, `bushfire`, `ecology`, `heritage`, `acoustic`, `social`,
`economic`, `aboriginal_heritage`, `contamination`, `flood`,
`urban_design`, `infrastructure`, `coastal`, `null`

### Implementation

- Primary signal: `documents.category` → tier mapping (dict lookup)
- Secondary signal: title keyword scan for concern tag
- "Other" category (52 docs): classify by title keywords, fallback to Tier 3
- Log any doc that doesn't match → manual review
- Target: <5% unknown rate

### Acceptance test

```sql
SELECT tier, COUNT(*) FROM documents GROUP BY tier;
-- Tier 1: ~25-50, Tier 2: ~80-120, Tier 3: rest

SELECT concern_tag, COUNT(*) FROM documents
WHERE tier = 2 GROUP BY concern_tag;
-- Every Tier 2 doc should have a non-null concern_tag
```

## Step 2: PDF text extraction (extract.py)

**Input:** PDF files for Tier 1 documents (then Tier 2).
**Output:** `chunks` table populated with page-level text.

### Implementation requirements

**PDF audit first (before writing code):**
- Pick 3 representative PDFs: one small council-led, one large council-led
  (Dural PP-2024-450), one State-led (Kurnell PP-2023-2828)
- Run pdfplumber on each: check page count, text extraction quality,
  presence of tables/figures
- Classify each as: native text, scan (needs OCR), or mixed
- This audit determines whether OCR is needed in week 2 or deferred

**Extraction logic:**
- Use pdfplumber for all native-text PDFs
- Extract text page by page
- Chunk by page (one chunk = one page). Don't over-engineer chunking yet.
  Page-level gives natural citation grounding. Refine later if retrieval
  quality suffers.
- For each chunk: store document_id, pp_number, page_number, chunk_index,
  text, char_count
- If a page yields <50 chars, mark extraction_method as 'failed' (likely
  scan or image page) — don't silently produce empty chunks
- Skip OCR for now. Log scanned pages. Add OCR later if it matters for
  high-value docs.

**Progress tracking:**
- Process Tier 1 docs first (~25-50 PDFs, the actual proposals)
- Then Tier 2 (~80-120 PDFs, technical studies)
- Tier 3 can wait — admin docs rarely matter for briefs

### Acceptance test

```sql
SELECT p.pp_number, COUNT(c.id) AS chunks,
       SUM(c.char_count) AS total_chars
FROM pps p
JOIN documents d ON d.pp_number = p.pp_number
JOIN chunks c ON c.document_id = d.id
WHERE d.tier = 1
GROUP BY p.pp_number;
-- Every PP (except PP-2025-1092) should have chunks
```

## Step 3: Embeddings + retrieval (embed.py, retrieve.py)

**Input:** `chunks` table.
**Output:** ChromaDB vector store + `retrieve()` function.

### Implementation requirements

**Embedding:**
- Model: `text-embedding-3-small` (OpenAI) or `BAAI/bge-small-en-v1.5`
  (local via sentence-transformers). Pick one. Local preferred for cost
  at this scale (thousands of chunks).
- Store in ChromaDB with persistent directory at `data/chroma/`
- Metadata per vector: chunk_id, document_id, pp_number, page_number,
  document_title, category, tier

**Retrieval function:**

```python
def retrieve(
    pp_number: str,
    query: str,
    k: int = 5,
    tier_filter: list[int] | None = None,
) -> list[dict]:
    """Return top-k chunks for a PP matching the query.

    Each result dict contains:
      chunk_id, text, page_number, document_title, category, tier,
      similarity_score
    """
```

- Filter by pp_number (always) and optionally by tier
- Return chunk text + full grounding metadata

### Acceptance test

```python
results = retrieve("PP-2023-2828", "proposed building heights")
# Should return chunks from the Kurnell EIE/rezoning proposal
# with page numbers that actually discuss heights

results = retrieve("PP-2024-450", "traffic impact")
# Should return chunks from Dural traffic study
```

## Step 4: Brief generator (brief.py)

**Input:** PP number → retrieval function → LLM pipeline.
**Output:** Markdown brief with inline citations.

### Pipeline design (LangGraph)

Five nodes, serial:

1. **Orient** — Load PP metadata from manifest. Retrieve Tier 1 chunks.
   Classify PP type (council-led vs State-led, based on
   `relevant_planning_authority`). Identify what the proposal is about
   from the title + description.

2. **Draft sections** — For each of three sections:
   - "What's being proposed" — use Tier 1 chunks (the actual proposal)
   - "What changes on the ground" — use Tier 1 + Tier 2 chunks
   - "Things to know" — use Tier 2 chunks (technical studies, concerns)

   Generate 1-2 paragraphs per section. Every factual sentence MUST
   include a citation: `[doc:<title>, p.<page>]`. The LLM receives
   chunk text with metadata and must cite from what it's given.

3. **Verify** — For each citation in the draft, check: does the cited
   chunk actually support the claim? Use a separate LLM call with just
   the claim + the cited chunk text. Output: verified / unsupported /
   partially_supported.

4. **Rewrite** — For unsupported citations: try to find a better chunk
   via retrieval. If found, rewrite the sentence with the correct
   citation. If not, drop the claim entirely. Never leave an unsupported
   citation.

5. **Compose** — Assemble final markdown brief. Add a references section
   at the bottom mapping citation keys to full document titles + SHA256
   paths. Store in `briefs` table with citations_json for traceability.

### LLM configuration

- Use Claude (claude-sonnet-4-20250514) for draft and rewrite nodes
- Use Claude Haiku for verify node (cheaper, just yes/no judgment)
- System prompt must instruct: "You are writing a plain-language summary
  for a non-expert resident. No jargon. Every factual claim must cite
  its source."

### Iteration strategy

- Build and test on Kurnell (PP-2023-2828) ONLY first. It's the most
  complex PP (State-led, 37 docs, 2.5 GB). If it works on Kurnell, it
  works on everything.
- Second test: a small council-led PP (PP-2025-2427, Shellharbour, 2 docs)
  to verify the pipeline handles minimal input gracefully.
- Third test: a medium council-led PP (PP-2024-450, Dural, 25 docs).
- Only after all three produce good briefs: run on all 23 PPs.

### Acceptance test

Print the Kurnell brief. Read every sentence. For each factual claim:
1. Find the cited document in data/documents/
2. Open to the cited page
3. Verify the text supports the claim

If any citation is wrong or unsupported, fix the pipeline. Repeat until
every citation resolves correctly.

## Dependencies (additions to pyproject.toml)

    pdfplumber>=0.11
    chromadb>=0.5
    sentence-transformers>=3.0    # if using local embeddings
    langgraph>=0.2
    anthropic>=0.40               # for Claude API calls

## What NOT to do

- Do not add OCR in the first pass. Log scanned pages, handle later.
- Do not chunk below page level initially. Page = chunk = citation unit.
  Refine only if retrieval quality demands it.
- Do not run the brief generator on all 23 PPs until it works on 3.
- Do not build a web UI yet. Markdown output is the deliverable.
- Do not fine-tune embeddings. Off-the-shelf model first.
- Do not parallelize extraction or embedding. Serial is fine at this scale.
- Do not add streaming or real-time features. Batch pipeline only.

## Start here

1. Run pdfplumber audit on 3 representative PDFs (5 mins).
2. Implement classify.py, populate tier + concern_tag (30 mins).
3. Implement extract.py, process Tier 1 docs (1 evening).
4. Implement embed.py + retrieve.py (1 evening).
5. Build brief.py orient + draft nodes, test on Kurnell (1 evening).
6. Add verify + rewrite nodes (1 evening).
7. Test on Shellharbour + Dural. Fix issues.
8. Run on all 23 PPs.
9. Manual review of 3 briefs. Fix pipeline until citations are solid.

## Testing approach

No formal test suite. The test is output quality:
- Tier distribution matches expectations
- Every Tier 1 doc has chunks
- Retrieval returns relevant chunks for known queries
- Brief citations resolve to real pages with supporting text
- Manual read of 3 briefs finds zero unsupported claims
