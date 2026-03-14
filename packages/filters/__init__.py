"""Executive-level title pre-filter — fast gate to discard irrelevant jobs.

Applied in the pipeline **before** normalization so that the expensive
normalizer and scoring engine only process plausibly relevant postings.

The filter uses two regex passes:

1. **Seniority gate** — Does the title contain a senior-level prefix
   (VP, Director, Head of, Chief, SVP, General Manager, President, …)?
2. **Junior reject** — Does the title contain obviously junior markers
   (Intern, Associate, Coordinator, Analyst, Specialist, …) *without*
   an overriding seniority prefix?

Jobs with titles that pass the seniority gate OR don't trigger the
junior reject are kept; everything else is discarded.  This typically
removes 70–85 % of postings from general-purpose job boards.
"""

from __future__ import annotations

import logging
import re

from packages.schemas.raw_job import RawJobPosting

logger = logging.getLogger(__name__)

# ── Seniority prefixes that always pass the filter ────────────────
_EXEC_TITLE_RE = re.compile(
    r"""(?ix)                         # case-insensitive, verbose
    \b(?:
        chief | ceo | coo | cfo | cto | cio | cpo | cso
        | president
        | [es]?vp\b | vice\s+president
        | director
        | head\s+of
        | general\s+manager
        | managing\s+director
        | partner
        | principal
        | fellow
        | group\s+lead(?:er)?
        | senior\s+director
        | executive
    )\b
    """,
)

# ── Junior markers — reject if no exec prefix overrides ───────────
_JUNIOR_REJECT_RE = re.compile(
    r"""(?ix)
    \b(?:
        intern(?:ship)?
        | trainee
        | apprentice
        | junior
        | entry[\s\-]?level
        | associate(?!\s+director|\s+vice|\s+general)
        | coordinator
        | representative
        | clerk
        | receptionist
        | assistant(?!\s+(?:vice|general)\s+(?:president|manager))
        | technician
        | operator\b
    )\b
    """,
)

# ── Mid-level roles that are unlikely to be relevant ──────────────
_MID_REJECT_RE = re.compile(
    r"""(?ix)
    \b(?:
        analyst
        | specialist
        | administrator
        | accountant
        | bookkeeper
        | recruiter
        | designer(?!\s+director)
        | developer
        | engineer(?!\s+(?:director|vice|vp|head))
        | scientist(?!\s+(?:director|vice|vp|head))
        | nurse | physician | therapist | counselor
        | teacher | instructor | professor
        | paralegal | legal\s+assistant
        | cashier | teller
    )\b
    """,
)


def is_executive_title(title: str) -> bool:
    """Return True if the title looks executive-level or senior enough."""
    if _EXEC_TITLE_RE.search(title):
        return True
    # Not exec-level: check if it's clearly junior/mid
    if _JUNIOR_REJECT_RE.search(title):
        return False
    if _MID_REJECT_RE.search(title):
        return False
    # Unknown seniority — keep (could be "Plant Manager", "Program Lead", etc.)
    return True


def filter_executive_postings(
    postings: list[RawJobPosting],
) -> list[RawJobPosting]:
    """Filter a list of raw postings to only executive-level titles.

    Returns the filtered list.  Logs how many were discarded.
    """
    kept = [p for p in postings if is_executive_title(p.title)]
    discarded = len(postings) - len(kept)
    if discarded:
        logger.info(
            "Title pre-filter: kept %d / %d postings (discarded %d)",
            len(kept),
            len(postings),
            discarded,
        )
    return kept
