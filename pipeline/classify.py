"""Document classifier: assign tier (1/2/3) and concern_tag to each document.

Tier 1: The actual planning proposal / exhibition documents
Tier 2: Technical studies and evidence (traffic, heritage, ecology, etc.)
Tier 3: Administrative / process documents (gateway, council reports, etc.)

Primary signal: portal category. Secondary: title keywords for "Other" category
and concern_tag assignment.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from scraper.models import Document

logger = logging.getLogger(__name__)

# --- Category -> Tier mapping ---

CATEGORY_TIER: dict[str, int] = {
    # Tier 1: the actual proposal
    "Proposal for Public Exhibition": 1,
    "Draft Planning Proposal": 1,
    "Planning Proposal for agency consultation": 1,
    "Planning Proposal post exhibition - revised": 1,
    "Exhibition Documents": 1,
    "Planning Proposal for Gateway determination": 1,

    # Tier 2: technical studies / evidence
    "Acoustic report": 2,
    "Traffic report": 2,
    "Heritage Impact Assessment": 2,
    "Flora and Fauna Report": 2,
    "Contamination and/or remediation action plan": 2,
    "Aboriginal Cultural Heritage Assessment Report": 2,
    "Flood risk management report": 2,
    "Bushfire report": 2,
    "Urban design and built form assessment": 2,
    "Infrastructure assessment": 2,
    "Technical Studies": 2,
    "Retail assessment": 2,
    "Draft Development Control Plan": 2,
    "Coastal Design Guidelines Assessment Checklist for Planning Proposals": 2,
    "State Significant Rezoning Evaluation Panel": 2,
    "Draft Development Control Plan": 2,

    # Tier 3: admin / process
    "Gateway determination": 3,
    "Gateway determination report": 3,
    "Gateway letter to council": 3,
    "Gateway Alteration document": 3,
    "Council report and resolution": 3,
    "Record of decision": 3,
    "Record of decision PPAAppointment": 3,
    "Completed declaration form RR": 3,
    "Owner's consent": 3,
    "Planning Proposal maps": 3,
    "Map of the applicable land area": 3,
    "Plans": 3,
}

# --- Category -> Concern tag ---

CATEGORY_CONCERN: dict[str, str] = {
    "Acoustic report": "acoustic",
    "Traffic report": "traffic",
    "Heritage Impact Assessment": "heritage",
    "Flora and Fauna Report": "ecology",
    "Contamination and/or remediation action plan": "contamination",
    "Aboriginal Cultural Heritage Assessment Report": "aboriginal_heritage",
    "Flood risk management report": "flood",
    "Bushfire report": "bushfire",
    "Urban design and built form assessment": "urban_design",
    "Infrastructure assessment": "infrastructure",
    "Retail assessment": "economic",
    "Coastal Design Guidelines Assessment Checklist for Planning Proposals": "coastal",
    "Draft Development Control Plan": "urban_design",
}

# --- Title keyword patterns for "Other" category and concern_tag fallback ---

TITLE_TIER_PATTERNS: list[tuple[str, int, str | None]] = [
    # (regex, tier, concern_tag or None)
    # Order matters: Tier 3 admin patterns first to prevent false Tier 1 matches
    # on titles like "Council Minutes - Planning Proposal..."

    # Tier 3 indicators (check BEFORE Tier 1)
    (r"council\s+minut", 3, None),
    (r"council\s+resolution", 3, None),
    (r"gateway\s+determin", 3, None),
    (r"gateway\s+request", 3, None),
    (r"record\s+of\s+decision", 3, None),
    (r"confirmed\s+minutes", 3, None),

    # Tier 1 indicators
    (r"planning\s+proposal", 1, None),
    (r"exhibition\s+fact\s+sheet", 1, None),
    (r"fact\s+sheet", 1, None),
    (r"frequently\s+asked|FAQ", 1, None),
    (r"re-?exhibition", 1, None),
    (r"explanation\s+of\s+intended\s+effect", 1, None),
    (r"rezoning\s+proposal", 1, None),
    (r"master\s+plan", 1, None),

    # Tier 2 indicators
    (r"traffic|transport\s+impact|parking\s+report", 2, "traffic"),
    (r"pedestrian\s+wind", 2, "urban_design"),
    (r"acoustic|noise|sound", 2, "acoustic"),
    (r"heritage|ahims", 2, "heritage"),
    (r"aboriginal|indigenous", 2, "aboriginal_heritage"),
    (r"bushfire", 2, "bushfire"),
    (r"flood|stormwater", 2, "flood"),
    (r"ecolog|biodiversity|flora|fauna", 2, "ecology"),
    (r"contaminat|soil\s+character|remediat|site\s+investigation", 2, "contamination"),
    (r"urban\s+design|built\s+form|shadow", 2, "urban_design"),
    (r"infrastructure\s+(servic|assess)", 2, "infrastructure"),
    (r"economic|retail\s+assess", 2, "economic"),
    (r"social\s+impact", 2, "social"),
    (r"visual\s+impact", 2, "urban_design"),
    (r"landslip|geotech", 2, "contamination"),
    (r"construction\s+management", 2, "infrastructure"),
    (r"sustainability\s+strategy", 2, "infrastructure"),
    (r"public\s+art\s+plan", 2, "urban_design"),
    (r"engagement\s+report|consultation", 2, "social"),
    (r"conservation\s+zone", 2, "ecology"),
    (r"employment\s+lands?\s+study", 2, "economic"),
    (r"air\s+quality", 2, "contamination"),
    (r"coastal\s+management", 2, "coastal"),
    (r"landscape.*open\s+space|open\s+space.*strategy", 2, "urban_design"),
    (r"site\s+audit\s+statement", 2, "contamination"),
    (r"transport.*assessment|transport.*strategy", 2, "traffic"),
    (r"design\s+guideline", 2, "urban_design"),
    (r"connecting\s+with\s+country", 2, "aboriginal_heritage"),
    (r"community\s+engagement|engagement.*outcome", 2, "social"),
    (r"widening\s+diagram", 2, "traffic"),
    (r"panel\s+report", 2, None),
    (r"industrial\s+lands", 2, "economic"),
    (r"early\s+engagement|engagement\s+action", 2, "social"),
    (r"concept\s+subdivision", 2, "urban_design"),
    (r"statement\s+of\s+council\s+interest", 3, None),
    (r"rezoning\s+letter", 3, None),
    (r"appendices\s+for\s+PP", 1, None),
    (r"resource\s+hub.*report|final\s+report", 2, "infrastructure"),
    (r"prop\s+sub", 3, None),
    (r"UGA\s+VR|viability\s+report", 2, "economic"),
    (r"local\s+planning\s+panel\s+report", 3, None),

    # Tier 3 indicators (continued)
    (r"council\s+report", 3, None),
    (r"local\s+planning\s+panel", 3, None),
    (r"caveat|title", 3, None),
    (r"letter\s+to\s+(dphi|council|department)", 3, None),
    (r"government\s+gazette", 3, None),
    (r"practice.?note", 3, None),
    (r"record\s+of\s+decision", 3, None),
    (r"RFS.*determination|determination\s+letter", 3, None),
    (r"confirmed\s+minutes", 3, None),
    (r"reclassification.*assessment|assessment.*reclassification", 3, None),
    (r"LEP.*mapping|mapping.*extract", 3, None),
    (r"land\s+use\s+matrix", 3, None),
    (r"comparison.*LEP|comparision", 3, None),
    (r"written\s+instrument", 3, None),
    (r"land\s+acquisition", 3, None),
    (r"council\s+owned\s+land", 3, None),
    (r"public\s+hearing", 3, None),
    (r"implementation\s+action\s+plan", 3, None),
]


def classify_by_category(category: str | None) -> tuple[int | None, str | None]:
    """Classify by portal category. Returns (tier, concern_tag)."""
    if not category:
        return None, None
    tier = CATEGORY_TIER.get(category)
    concern = CATEGORY_CONCERN.get(category)
    return tier, concern


def classify_by_title(title: str) -> tuple[int | None, str | None]:
    """Classify by title keywords. Returns (tier, concern_tag)."""
    for pattern, tier, concern in TITLE_TIER_PATTERNS:
        if re.search(pattern, title, re.I):
            return tier, concern
    return None, None


def classify_document(doc: Document) -> tuple[int, str | None]:
    """Classify a single document. Returns (tier, concern_tag).

    Strategy:
    1. Check title first — it's specific and catches misfilings
       (e.g. a heritage assessment filed under "Proposal for Public Exhibition")
    2. If title gives a Tier 2 or Tier 3 match, trust it over category
    3. If title gives no match, fall back to category
    4. If neither matches, default to Tier 3
    """
    title = doc.title or ""
    title_tier, title_concern = classify_by_title(title)
    cat_tier, cat_concern = classify_by_category(doc.category)

    # Title says Tier 2 or Tier 3 → trust title (catches misfiled docs)
    if title_tier is not None and title_tier >= 2:
        return title_tier, title_concern

    # Title says Tier 1 → use it, but grab concern from either source
    if title_tier == 1:
        return 1, title_concern or cat_concern

    # Title gave nothing → use category
    if cat_tier is not None:
        # Category gave a tier, try to enrich concern from title
        concern = cat_concern or title_concern
        return cat_tier, concern

    # Neither matched
    logger.warning(
        "Unclassified doc: pp=%s category=%r title=%r -> defaulting to Tier 3",
        doc.pp_number, doc.category, doc.title,
    )
    return 3, None


def classify_all(session: Session) -> dict[str, int]:
    """Classify all documents. Returns summary stats."""
    docs = session.query(Document).all()
    stats: dict[str, int] = {"total": len(docs), "tier_1": 0, "tier_2": 0, "tier_3": 0, "unclassified": 0}

    for doc in docs:
        tier, concern = classify_document(doc)
        doc.tier = tier
        doc.concern_tag = concern

        if tier == 1:
            stats["tier_1"] += 1
        elif tier == 2:
            stats["tier_2"] += 1
        elif tier == 3:
            stats["tier_3"] += 1

    session.commit()
    return stats


def print_classification_report(session: Session) -> None:
    """Print a detailed classification report."""
    from sqlalchemy import func

    print("\n" + "=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)

    # Tier distribution
    for tier in [1, 2, 3]:
        count = session.query(Document).filter_by(tier=tier).count()
        print(f"Tier {tier}: {count} documents")

    # Concern tag distribution (Tier 2 only)
    print("\nTier 2 concern tags:")
    rows = (
        session.query(Document.concern_tag, func.count())
        .filter_by(tier=2)
        .group_by(Document.concern_tag)
        .order_by(func.count().desc())
        .all()
    )
    for tag, count in rows:
        print(f"  {tag or '(none)':25s} {count}")

    # Any Tier 2 without concern tag?
    no_concern = session.query(Document).filter_by(tier=2, concern_tag=None).count()
    if no_concern:
        print(f"\n  WARNING: {no_concern} Tier 2 docs with no concern tag")

    # Unclassified (shouldn't happen, but check)
    no_tier = session.query(Document).filter_by(tier=None).count()
    if no_tier:
        print(f"\n  WARNING: {no_tier} docs with no tier")

    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from scraper.models import create_db_engine, create_session
    engine = create_db_engine()
    session = create_session(engine)

    stats = classify_all(session)
    print(f"\nClassified {stats['total']} documents:")
    print(f"  Tier 1 (proposals):  {stats['tier_1']}")
    print(f"  Tier 2 (technical):  {stats['tier_2']}")
    print(f"  Tier 3 (admin):      {stats['tier_3']}")

    print_classification_report(session)
    session.close()
