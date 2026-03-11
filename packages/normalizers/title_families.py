"""Title-family normalization — maps executive titles to canonical families.

Each family groups synonymous or near-synonymous titles so the ranker
can compare postings against the target profile at a semantic level
rather than relying on fragile substring matching alone.

Usage::

    from packages.normalizers.title_families import resolve_title_family

    family = resolve_title_family("Chief Operating Officer")
    # => "COO"
"""

from __future__ import annotations

import re

# ── Title family definitions ──────────────────────────────────────
# Each entry maps a canonical family name to a list of regex patterns
# that match titles belonging to that family.  Patterns are evaluated
# in order; the first match wins.

_TITLE_FAMILIES: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "COO",
        [
            re.compile(
                r"\b(?:chief\s+operat\w*|coo)\b", re.IGNORECASE,
            ),
        ],
    ),
    (
        "CEO",
        [
            re.compile(
                r"\b(?:chief\s+executive\w*|ceo)\b", re.IGNORECASE,
            ),
        ],
    ),
    (
        "CFO",
        [
            re.compile(
                r"\b(?:chief\s+financial\w*|cfo)\b", re.IGNORECASE,
            ),
        ],
    ),
    (
        "CTO",
        [
            re.compile(
                r"\b(?:chief\s+technolog\w*|cto)\b", re.IGNORECASE,
            ),
        ],
    ),
    (
        "CHRO",
        [
            re.compile(
                r"\b(?:chief\s+human\w*|chief\s+people\w*|chro)\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "CMO",
        [
            re.compile(
                r"\b(?:chief\s+market\w*|cmo)\b", re.IGNORECASE,
            ),
        ],
    ),
    (
        "CSO",
        [
            re.compile(
                r"\b(?:chief\s+strateg\w*|chief\s+sustainab\w*|cso)\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "VP_OPERATIONS",
        [
            re.compile(
                r"\b(?:svp|senior\s+vice\s+president|vp|"
                r"vice\s+president)\s+(?:of\s+)?operat",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "VP_MANUFACTURING",
        [
            re.compile(
                r"\b(?:svp|senior\s+vice\s+president|vp|"
                r"vice\s+president)\s+(?:of\s+)?manufact",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "VP_SUPPLY_CHAIN",
        [
            re.compile(
                r"\b(?:svp|senior\s+vice\s+president|vp|"
                r"vice\s+president)\s+(?:of\s+)?supply\s+chain",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "VP_ENGINEERING",
        [
            re.compile(
                r"\b(?:svp|senior\s+vice\s+president|vp|"
                r"vice\s+president)\s+(?:of\s+)?engineer",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "VP_QUALITY",
        [
            re.compile(
                r"\b(?:svp|senior\s+vice\s+president|vp|"
                r"vice\s+president)\s+(?:of\s+)?qualit",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "HEAD_OPERATIONS",
        [
            re.compile(
                r"\b(?:head\s+of|director\s+of)\s+operat",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "HEAD_MANUFACTURING",
        [
            re.compile(
                r"\b(?:head\s+of|director\s+of)\s+manufact",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "HEAD_SUPPLY_CHAIN",
        [
            re.compile(
                r"\b(?:head\s+of|director\s+of)\s+supply\s+chain",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "HEAD_QUALITY",
        [
            re.compile(
                r"\b(?:head\s+of|director\s+of)\s+qualit",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "HEAD_TRANSFORMATION",
        [
            re.compile(
                r"\b(?:head\s+of|director\s+of)\s+(?:business\s+)?transform",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "PLANT_DIRECTOR",
        [
            re.compile(
                r"\b(?:plant\s+(?:director|manager)|"
                r"site\s+(?:director|manager)|"
                r"factory\s+(?:director|manager))\b",
                re.IGNORECASE,
            ),
        ],
    ),
    (
        "GM_OPERATIONS",
        [
            re.compile(
                r"\b(?:general\s+manager)\b.*\b(?:operat|manufact|industr)",
                re.IGNORECASE,
            ),
        ],
    ),
]

# Families considered "operations-adjacent" for scoring purposes
OPERATIONS_FAMILIES: frozenset[str] = frozenset(
    {
        "COO",
        "VP_OPERATIONS",
        "VP_MANUFACTURING",
        "VP_SUPPLY_CHAIN",
        "VP_QUALITY",
        "HEAD_OPERATIONS",
        "HEAD_MANUFACTURING",
        "HEAD_SUPPLY_CHAIN",
        "HEAD_QUALITY",
        "HEAD_TRANSFORMATION",
        "PLANT_DIRECTOR",
        "GM_OPERATIONS",
    }
)

# Families that are C-suite but not operations
NON_OPS_CSUITE: frozenset[str] = frozenset(
    {"CFO", "CTO", "CHRO", "CMO", "CSO"}
)


def resolve_title_family(title: str) -> str | None:
    """Return the canonical family name for *title*, or ``None``."""
    for family, patterns in _TITLE_FAMILIES:
        for pat in patterns:
            if pat.search(title):
                return family
    return None
