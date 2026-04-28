# Task: Implement Layer 1 + Layer 2 fact verification for the brief generator

## Context

We have a working pipeline that generates plain-English briefs about NSW Planning
Proposals. Each brief is grounded by retrieving chunks from source PDFs and
asking an LLM to write prose with inline citations like:

    [doc: Explanation of Intended Effects | p.5]

After generation, an existing verifier checks that each cited chunk exists and
is topically related to the claim. It currently reports "Citation accuracy:
N/N verified" — but this only confirms citations resolve, not that the
**specific facts asserted in the claim actually appear in the cited source**.

Real failures we've seen in our briefs:

- "140 hectares of green space" cited to a source that says "116 hectares"
- "approximately 30,071 m²" — a precise number paired with a hedge, suggesting
  LLM uncertainty
- "16-metre height limits for some areas" — number is in source but applies
  only to Lots 8 and 9, not "some areas" generically
- A reference to "the 2021 Employment Lands Study" where the date should be
  spot-checked

We need a two-layer fact verification step that runs after the existing
citation verification, before the brief is finalised.

## What this verifier IS for

In-scope categories of fact:

- **Numbers with units**: heights, areas, ratios, percentages, dwelling
  counts, distances, durations
- **Years and dates**: study years, target completion dates, exhibition dates,
  publication years
- **Identifiers**: PP numbers (PP-YYYY-NNNN), Lot/DP numbers, zone codes
  (R2, RU6, E1, etc.), clause references, LEP/SEPP names with year suffix
- **Money**: dollar amounts and thresholds
- **Directional claims about change**: "reduced from X to Y", "increased
  from X to Y", "removes the requirement", "introduces the cap" — only when
  X and Y are extractable concrete facts (numbers, codes, identifiers)
- **Scope qualifiers attached to facts**: "for Lots 8 and 9", "in the Town
  Centre Precinct", "across the site" — only when adjacent to a verifiable
  fact

## What this verifier is NOT for

Out of scope, do NOT extract or escalate:

- **Descriptive prose without verifiable anchors**: "the proposal aims to
  revitalise the corner", "the changes will encourage more investment",
  "this would create a vibrant new community" — vague intent claims, no
  facts to check
- **Comparison verbs in non-quantitative context**: "this matches other
  general industrial areas" should NOT trigger comparison-verb extraction
  because there's no X-to-Y to verify
- **Council/authority names in metadata fields**: the brief's `Council` and
  `Address` metadata fields are populated by the scraper, not the brief
  generator. Errors there are scraping issues, not verification issues.
  Do NOT verify metadata fields. ONLY verify facts that appear inside the
  prose body of the brief.
- **Generic capitalised phrases that aren't named entities**: "Local
  Government Area", "Planning Proposal", "Stage 1" — these are categories,
  not entities to verify
- **Vague scope phrases without an attached fact**: "in some areas", "across
  the site", "throughout the precinct" — only escalate scope when it's
  attached to a specific quantitative or identified fact (a number, a zone
  code, a comparison)

The goal: Layer 1 should be **selective**, not exhaustive. If a claim has no
clean, deterministically-verifiable anchor, return `no_facts` and skip it.
A descriptive sentence with no extractable facts is the citation verifier's
problem, not ours.

## Architecture

Two layers run in sequence per claim:

### Layer 1: Conservative deterministic fact extraction (no LLM)

Run only the extractors below. Each pattern produces a candidate fact; each
candidate is then **filtered** against the rules in "Suppression rules"
before being kept.

**Patterns to extract (high-precision only):**

- Numbers with explicit units:
    `\b\d+(?:[.,]\d+)?\s*(m²|m2|metres?|m\b|sqm|hectares?|ha|%|storeys?|kilometres?|km|dwellings?|homes?)\b`
- Ratios: `\b\d+(?:\.\d+)?:\d+(?:\.\d+)?\b`
- Years: `\b(19|20)\d{2}\b`  (only when adjacent to a noun like "study",
  "plan", "report", "amendment", or a date context — not bare years floating
  in prose)
- Dates: `\b\d{1,2}/\d{1,2}/\d{4}\b` and
  `\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b`
- PP numbers: `\bPP-\d{4}-\d+\b`
- Lot/DP numbers: `\bLot\s+\d+\s+(in\s+)?DP\s*\d+\b`
- Zone codes (only with NSW LEP standard prefixes):
  `\b(R[1-5]|RU[1-6]|RE[1-2]|E[1-4]|SP[1-3]|MU\d|C[1-4]|B[1-8])\b(?=\s|[,.;:])`
- Clause references: `\b(Clause|Section|Schedule)\s+\d+(?:\.\d+)*[A-Z]?\b`
- Money amounts: `\$\d+(?:[.,]\d+)?\s*(million|m|billion|b)?\b`

**Patterns NOT to extract** (too noisy, too descriptive):

- Generic comparison verbs alone — only treat "increase/reduce/remove/
  introduce" as a fact when paired with explicit X-to-Y values within the
  same sentence
- Capitalised proper nouns alone — councils, applicants, consultancies are
  often correct in prose but vary in completeness; skip them
- Scope markers alone — only treat scope as a fact when it appears within
  20 characters of a verifiable extracted fact (number, zone code, lot)

**Suppression rules (applied AFTER pattern matching):**

1. If a number's "unit" is "m" but the surrounding context contains the word
   "million" or "metropolitan" or "MU", drop it (likely false positive on
   another token).
2. If a year appears with no nearby noun anchoring it as a date (within 30
   characters: "study", "plan", "report", "in", "by", "since", "from",
   "amendment", "version", "edition", "published"), drop it.
3. If a zone code candidate is preceded by the word "the" with no other
   zone-context cue, drop it (false match on "the R" type substrings).
4. If a number is part of an obvious phrase that isn't a planning fact
   ("Stage 1", "Stage 2", "Part 1", "Section 1" already caught above),
   drop it.

**Matching logic:**

For each extracted fact, check the cited chunk for support:

- Numbers and ratios: normalise (strip thousands separators, harmonise unit
  aliases like "square metres" → "m²", "hectares" → "ha") and substring
  match against the chunk's normalised text. Allow ±0% tolerance for plain
  numbers; allow ±5% only when claim contains "approximately", "around",
  "about", or "roughly".
- Years and dates: exact substring match.
- Identifiers: case-insensitive substring match.
- Money: normalise to base form and substring match.
- Directional change facts: BOTH the X-value AND the Y-value must appear in
  chunk; layer 1 cannot verify direction, so escalate to Layer 2.

**Layer 1 outcomes:**

- **verified**: every extracted fact has a clean, unambiguous match
- **unsupported**: at least one extracted fact has NO match in chunk
- **ambiguous**: facts found but with potential misattribution or
  directionality concerns (escalate to Layer 2)
- **no_facts**: no facts passed extraction + suppression filters → skip
  verification, claim is the citation verifier's problem

**Escalation triggers (ambiguous → Layer 2):**

- A matching number is found, but the chunk contains 2+ other numbers with
  the same unit within 200 characters (potential misattribution)
- Claim contains "from X to Y" or "between X and Y" with both X and Y
  matched in chunk (need direction check)
- Claim contains "approximately"/"around"/"about" + a precise number AND
  the chunk's exact value differs from the claim's (need to verify the
  rounding is reasonable)
- Claim contains a scope qualifier ("for Lots 8 and 9", "in the Town Centre")
  immediately attached to a verifiable fact, AND the chunk has the fact but
  in different stated scope

Anything else that would cause Layer 1 to be uncertain → just return
`unsupported` and let the rewrite loop deal with it. Don't escalate
borderline cases.

### Layer 2: LLM verification on ambiguous cases (Gemini 2.5 Flash)

For each Layer 1 ambiguous case, one Gemini Flash call.

System prompt:

    You are a fact-checker for planning document briefs. A claim and a cited
    source chunk are provided. The claim has been pre-flagged because it
    contains a directional change, a rounded number, or a scope qualifier
    that needs verification beyond simple string matching.

    Verify ONLY the specific aspects flagged. Do not look for other issues.

    For each flagged aspect, decide:
    1. Direction: if the claim says "from X to Y" (increased / reduced /
       changed), the chunk must support BOTH that X is the prior state and Y
       is the proposed state.
    2. Rounding: if the claim uses "approximately", "around", "about", the
       chunk's exact value must be within reasonable rounding of the claim's
       value. Round to a max of 2 significant figures of imprecision.
    3. Scope: if the claim attaches a fact to a specific scope ("for Lots 8
       and 9", "in the Town Centre Precinct", "across the site"), the chunk
       must support the same scope, not a narrower or broader one.

    Respond in this JSON format:

    {
      "verdict": "supported" | "unsupported" | "partially_supported",
      "issues_found": [
        {"aspect": "direction|rounding|scope", "issue": "<one line>"}
      ],
      "reasoning": "<one or two sentences>"
    }

User prompt:

    CLAIM: {claim_sentence}

    CITED SOURCE: {document_title}, page {page_number}

    CHUNK TEXT:
    {chunk_text}

    FLAGGED ASPECTS: {comma-separated list of aspects to check, e.g.
    "direction, scope"}

Settings: temperature=0, max_output_tokens=400, model "gemini-2.5-flash".

### Mapping Layer 2 verdicts

- `supported` → status="verified", layer_used="L2"
- `partially_supported` → status="unsupported", layer_used="L2",
  notes=concatenated issues
- `unsupported` → status="unsupported", layer_used="L2", notes=reasoning

## Module structure

`pipeline/verify_facts.py` exposing:

    async def verify_claim_facts(
        claim_sentence: str,
        chunk_text: str,
        chunk_metadata: dict,
    ) -> FactVerificationResult

    @dataclass
    class FactVerificationResult:
        status: Literal["verified", "unsupported", "ambiguous", "no_facts"]
        layer_used: Literal["L1", "L2", "skipped"]
        extracted_facts: list[ExtractedFact]
        notes: str
        cost_estimate_usd: float

    @dataclass
    class ExtractedFact:
        kind: Literal["number", "year", "date", "identifier", "money",
                      "directional"]
        raw: str
        normalized: str
        layer_1_status: Literal["matched", "missing", "escalate"]
        layer_1_notes: str

## Integration into LangGraph

Add `verify_facts` node after the existing citation verifier and before
compose:

1. Existing topical citation verifier runs (claim relevant to chunk).
2. New `verify_claim_facts` runs:
   - Layer 1 first
   - Layer 2 only if Layer 1 returns ambiguous
3. If verified or no_facts → keep claim
4. If unsupported → mark for rewrite, attach issues_found in context
5. Rewrite cycle (max 2 attempts), then drop claim with reason logged

## Reporting

Brief footer:

    *Citations resolved: 33/33. Facts verified: 38/41 (L1: 31, L2: 7).
    3 claims rewritten, 0 dropped.*

Per-PP audit log at `reports/<pp_number>_verification.json` with every claim,
every extracted fact, every layer used, and any issues found. This is the
diagnostic surface for tuning.

## Test cases

In `tests/test_verify_facts.py`:

1. **Number digit-mismatch**: claim "140 hectares" vs source "116 hectares"
   → L1 returns unsupported (number missing).

2. **Number ambiguous (range)**: claim "ranging from 0.2:1 to 2.5:1" vs
   chunk containing both ratios but also others nearby → L1 escalates,
   L2 confirms range correctness.

3. **Year correctly anchored**: claim "the 2021 Employment Lands Study" vs
   chunk containing "Hornsby Employment Lands Study (March 2021)" → L1
   verifies 2021 (anchored to "Study").

4. **Year suppressed (no anchor)**: claim "by 2031" floating in prose with
   no anchor noun nearby → L1 suppression rule kicks in, year not extracted,
   no verification needed.

5. **Identifier exact**: claim "Lot 133 DP 1081488" vs chunk → L1 verifies.

6. **Zone code with surrounding zone context**: claim "rezoned from RU6 to
   R2" vs chunk "rezoning from RU6 Rural Transition to R2 Low Density
   Residential" → L1 verifies both codes.

7. **Zone code false positive avoided**: claim "the R section of the
   document" → suppression rule drops "R" candidate, no_facts.

8. **Scope mismatch**: claim "16-metre height limits for some areas" vs
   chunk "16m for Lots 8 and 9" → L1 finds 16m, escalates due to scope
   qualifier, L2 returns partially_supported with scope issue.

9. **Direction wrong**: claim "increased from 16m to 9m" vs chunk
   describing height reduction → both 16 and 9 found in chunk, L1 escalates,
   L2 returns unsupported with direction issue.

10. **Pure description**: claim "the proposal aims to revitalise the corner"
    → no facts extracted, returns no_facts, no LLM call.

11. **Approximation**: claim "approximately 4,300 new homes" vs chunk
    "approximately 4,300 new homes" → L1 verifies (exact match including
    qualifier).

12. **Approximation with mismatch**: claim "approximately 4,500 new homes"
    vs chunk "approximately 4,300 new homes" → L1 finds neither exact 4,500
    nor a 5% match, returns unsupported.

## Cost expectations

For 23 PPs with ~12 fact-bearing claims each (others classified as
no_facts and skipped):

- Layer 1: free
- Layer 2 escalates on ~25-30% of fact-bearing claims (with the conservative
  extraction rules above) = ~80 calls at ~$0.0006 each = ~$0.05 per full batch
- Rewrite cycles: ~20 across the corpus = ~$0.10
- **Total per full pipeline run: well under $0.50**

Dev iteration: budget $2-3 for prompt tuning and edge case handling.

## Tuning expectations

After the first run on Kurnell, expect:

- ~50-70% of claims classified as `no_facts` (descriptive prose) — this is
  desired, not a bug. The extraction is intentionally conservative.
- ~20-30% of claims `verified` at L1 (clean factual claims with single
  unambiguous matches)
- ~10-20% escalating to L2 (ranges, directional changes, scope qualifiers)
- ~5-10% returning `unsupported` (real bugs to fix)

If your first run shows L2 escalating on 50%+ of claims, Layer 1 is too
aggressive and the suppression rules need tightening. Specifically check:
- Are bare years (without anchor nouns) being extracted? Tighten rule 2.
- Are zone-code-like substrings (e.g. "R" alone) being extracted? Tighten rule 3.
- Are descriptive numbers ("Stage 1", "Part 2") being extracted as facts?
  Add a suppression rule for sequence numbers.

If your first run shows almost everything classified as `no_facts`, Layer 1
is too conservative. Specifically check:
- Are numbers without explicit units being missed? Some claims phrase
  numbers without units in adjacent text — consider whether the claim
  context provides the unit.
- Are years that should be extracted being suppressed? Loosen rule 2.

## Acceptance criteria

1. Brief footer reports facts verified by category and layer.
2. Known-bad cases caught:
   - "140 hectares" vs "116 hectares" → L1 catches
   - "16-metre height limits for some areas" → L2 catches scope issue
3. Pure descriptive prose ("aims to revitalise") classified as `no_facts`,
   no LLM call made.
4. Per-PP verification audit log exists.
5. Total cost for full 23-PP run stays under $0.50.
6. L2 escalation rate stays under 30% of fact-bearing claims.
7. No false positives on bare years, zone-code-like substrings, or
   sequence numbers.

## Out of scope (explicitly)

- **Council and address metadata fields**. These are populated by the
  scraper from the portal HTML, not by the brief generator. Errors in those
  fields are a scraping issue and will be fixed in the scraping layer
  separately. Do not verify metadata.
- **Named entity verification** (council names, applicant names,
  consultancy names). Too noisy and high-effort relative to value.
- **Topical/relevance verification**. Already handled by the existing
  citation verifier.

## Start here

1. Build Layer 1 extractor with all patterns AND suppression rules.
2. Build Layer 1 matcher with normalisation.
3. Run on Kurnell brief alone. Inspect the audit log:
   - How many claims classified `no_facts`?
   - How many `verified`?
   - How many escalated to L2?
   If any classification is off, tune extraction/suppression rules first
   before adding L2.
4. Implement Layer 2 with the prompt above.
5. Re-run Kurnell. Confirm "140 hectares" gets caught and rewritten to
   "116 hectares" (or dropped after 2 rewrite attempts).
6. Run on Dural, Hornsby, Wagga, Grenfell.
7. If L2 escalation rate is over 30% on any PP, tighten Layer 1 first,
   not the L2 prompt.
8. Run on remaining 18 PPs.