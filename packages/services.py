"""Service assembly — builds configured pipeline components.

Centralizes component construction so route handlers and the worker
stay thin and don't import concrete implementations directly.

Collector choice is controlled by the ``EXEC_RADAR_COLLECTOR`` env var:

* ``mock`` (default) — synthetic sample data.
* ``greenhouse`` — real jobs from the Greenhouse Boards API.
* ``lever`` — real jobs from the Lever Postings API.
* ``ashby`` — real jobs from Ashby job boards.
* ``all`` — all real collectors (greenhouse + lever + ashby).
* ``greenhouse+lever`` — combine any types with ``+``.

In multi-collector mode (``all`` or ``+``-separated), each type reads
its own env vars.  Types that are not configured are silently skipped.
"""

from __future__ import annotations

import os
from pathlib import Path

from packages.collectors.ashby_collector import AshbyCollector
from packages.collectors.base import BaseCollector
from packages.collectors.composite_collector import CompositeCollector
from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.collectors.lever_collector import LeverCollector
from packages.collectors.mock_collector import MockCollector
from packages.normalizers.base import BaseNormalizer
from packages.normalizers.simple_normalizer import SimpleNormalizer
from packages.profile_loader import load_profile
from packages.rankers.base import BaseRanker
from packages.rankers.rule_based_ranker import RuleBasedRanker
from packages.schemas.target_profile import TargetProfile
from packages.source_sets import get_source_set

# Board token → human-readable company name
_BOARD_COMPANY_NAMES: dict[str, str] = {
    "samsungsemiconductor": "Samsung Semiconductor",
    "anellophotonics": "ANELLO Photonics",
    "andurilindustries": "Anduril Industries",
}

# Default boards when EXEC_RADAR_GREENHOUSE_BOARDS is not set
_DEFAULT_SEMICONDUCTOR_BOARDS = list(_BOARD_COMPANY_NAMES.keys())


# All real (non-mock) collector type names.
_REAL_COLLECTOR_TYPES = ["greenhouse", "lever", "ashby"]


def _build_from_source_set(ss_name: str) -> list[BaseCollector]:
    """Build collectors for all ATS types defined in a source set."""
    try:
        ss = get_source_set(ss_name)
    except KeyError as exc:
        raise ValueError(str(exc)) from None

    collectors: list[BaseCollector] = []
    for token, company in ss.boards.items():
        collectors.append(
            GreenhouseCollector(board_token=token, company_name=company)
        )
    for slug, _company in ss.lever_boards.items():
        collectors.append(LeverCollector(company_slug=slug))
    for slug, _company in ss.ashby_boards.items():
        collectors.append(AshbyCollector(company_slug=slug))
    return collectors


def _build_single_type(
    name: str,
    *,
    greenhouse_board: str | None = None,
    source_set: str | None = None,
    allow_unconfigured: bool = False,
) -> list[BaseCollector]:
    """Build collectors for a single type, returning a flat list.

    When *allow_unconfigured* is ``True`` (used in multi-type mode),
    types that lack required configuration return an empty list instead
    of raising.
    """
    if name == "mock":
        return [MockCollector()]

    if name == "greenhouse":
        # Source set resolves all ATS types it contains.
        ss_name = source_set or os.getenv("EXEC_RADAR_SOURCE_SET")
        if ss_name:
            return _build_from_source_set(ss_name)

        boards_str = (
            greenhouse_board
            or os.getenv("EXEC_RADAR_GREENHOUSE_BOARDS")
            or os.getenv("EXEC_RADAR_GREENHOUSE_BOARD")
        )
        if boards_str:
            tokens = [t.strip() for t in boards_str.split(",") if t.strip()]
        else:
            tokens = list(_DEFAULT_SEMICONDUCTOR_BOARDS)
        tokens_and_names: list[tuple[str, str | None]] = [
            (t, _BOARD_COMPANY_NAMES.get(t)) for t in tokens
        ]
        return [
            GreenhouseCollector(board_token=token, company_name=company)
            for token, company in tokens_and_names
        ]

    if name == "lever":
        slug = greenhouse_board or os.getenv("EXEC_RADAR_LEVER_COMPANY")
        if not slug:
            if allow_unconfigured:
                return []
            msg = (
                "Lever collector requires a company slug. "
                "Set EXEC_RADAR_LEVER_COMPANY or pass greenhouse_board."
            )
            raise ValueError(msg)
        slugs = [s.strip() for s in slug.split(",") if s.strip()]
        return [LeverCollector(company_slug=s) for s in slugs]

    if name == "ashby":
        slug = greenhouse_board or os.getenv("EXEC_RADAR_ASHBY_COMPANY")
        if not slug:
            if allow_unconfigured:
                return []
            msg = (
                "Ashby collector requires a company slug. "
                "Set EXEC_RADAR_ASHBY_COMPANY or pass greenhouse_board."
            )
            raise ValueError(msg)
        slugs = [s.strip() for s in slug.split(",") if s.strip()]
        return [AshbyCollector(company_slug=s) for s in slugs]

    msg = f"Unknown collector: {name!r}. Available: mock, greenhouse, lever, ashby, all"
    raise ValueError(msg)


def build_collector(
    collector_name: str | None = None,
    *,
    greenhouse_board: str | None = None,
    source_set: str | None = None,
) -> BaseCollector:
    """Return a collector based on *collector_name* or env vars.

    Supports single types (``"greenhouse"``), combined types
    (``"greenhouse+lever"``), and the ``"all"`` shortcut which includes
    every real collector type whose env vars are configured.

    Args:
        collector_name: Collector type(s). Falls back to
            ``EXEC_RADAR_COLLECTOR`` env var, then ``"mock"``.
        greenhouse_board: Board token / company slug (single type only).
        source_set: Named source set (single type only).

    Returns:
        A configured :class:`BaseCollector` instance.

    Raises:
        ValueError: If the collector name is unknown or nothing is
            configured in multi-type mode.
    """
    raw = (collector_name or os.getenv("EXEC_RADAR_COLLECTOR", "mock")).lower().strip()

    if raw == "all":
        types = list(_REAL_COLLECTOR_TYPES)
    elif "+" in raw:
        types = [t.strip() for t in raw.split("+") if t.strip()]
    else:
        types = [raw]

    if len(types) == 1:
        # Single type — pass through greenhouse_board and source_set.
        collectors = _build_single_type(
            types[0],
            greenhouse_board=greenhouse_board,
            source_set=source_set,
        )
    else:
        # Multi-type — each type reads its own env vars.
        # greenhouse_board / source_set only apply to greenhouse.
        collectors: list[BaseCollector] = []
        for t in types:
            kwargs: dict[str, str | None] = {}
            if t == "greenhouse":
                kwargs["greenhouse_board"] = greenhouse_board
                kwargs["source_set"] = source_set
            collectors.extend(
                _build_single_type(t, allow_unconfigured=True, **kwargs)
            )
        if not collectors:
            configured = ", ".join(types)
            msg = (
                f"No collectors configured for: {configured}. "
                "Set the required env vars for at least one type."
            )
            raise ValueError(msg)

    if len(collectors) == 1:
        return collectors[0]
    return CompositeCollector(collectors)


def build_normalizer() -> BaseNormalizer:
    """Return the default normalizer implementation."""
    return SimpleNormalizer()


def build_ranker(
    profile_path: str | Path | None = None,
    profile: TargetProfile | None = None,
) -> BaseRanker:
    """Return a ranker loaded with the given profile (or defaults).

    Args:
        profile_path: Optional path to a YAML profile file.
        profile: A pre-built TargetProfile (takes precedence over path).
    """
    if profile is None:
        profile = load_profile(profile_path)
    return RuleBasedRanker(profile=profile)


def build_pipeline_components(
    profile_path: str | Path | None = None,
    collector_name: str | None = None,
    *,
    greenhouse_board: str | None = None,
    profile: TargetProfile | None = None,
    source_set: str | None = None,
) -> tuple[BaseCollector, BaseNormalizer, BaseRanker]:
    """Build a complete set of pipeline components.

    Args:
        profile_path: Optional path to a YAML profile file.
        collector_name: Collector to use (``"mock"`` or ``"greenhouse"``).
        greenhouse_board: Greenhouse board token (if applicable).
        profile: A pre-built TargetProfile (takes precedence over path).
        source_set: Named source set. Falls back to the profile's
            ``preferred_source_set`` if set.

    Returns:
        A ``(collector, normalizer, ranker)`` tuple ready for
        :func:`packages.pipeline.run_pipeline`.
    """
    if profile is None:
        profile = load_profile(profile_path)
    resolved_source_set = source_set or profile.preferred_source_set or None
    return (
        build_collector(
            collector_name,
            greenhouse_board=greenhouse_board,
            source_set=resolved_source_set,
        ),
        build_normalizer(),
        build_ranker(profile_path=None, profile=profile),
    )


# ---------------------------------------------------------------------------
# Collector introspection (for dashboard status)
# ---------------------------------------------------------------------------

#: All supported collector types with display metadata.
AVAILABLE_COLLECTORS: list[dict[str, str]] = [
    {
        "name": "greenhouse",
        "label": "Greenhouse",
        "env_var": "EXEC_RADAR_GREENHOUSE_BOARD",
        "description": "Public Boards API",
    },
    {
        "name": "lever",
        "label": "Lever",
        "env_var": "EXEC_RADAR_LEVER_COMPANY",
        "description": "Public Postings API",
    },
    {
        "name": "ashby",
        "label": "Ashby",
        "env_var": "EXEC_RADAR_ASHBY_COMPANY",
        "description": "Embedded job board data",
    },
    {
        "name": "mock",
        "label": "Mock",
        "env_var": "",
        "description": "Synthetic sample data",
    },
]


def describe_collector(collector: BaseCollector) -> dict[str, str | list[str]]:
    """Return a dict describing the active collector for display.

    Keys:
        type: The collector type (``"greenhouse"``, ``"lever"``, etc.).
            ``"multi"`` when multiple types are combined.
        label: Human-readable label.
        sources: List of individual source names.
        active_types: Set of active collector type names.
    """
    source_name = collector.source_name

    if isinstance(collector, CompositeCollector):
        sources = source_name.split("+")
        # Detect which types are present
        types_present: set[str] = set()
        for s in sources:
            if s.startswith("greenhouse:"):
                types_present.add("greenhouse")
            elif s.startswith("lever:"):
                types_present.add("lever")
            elif "ashby" in s:
                types_present.add("ashby")
            else:
                types_present.add("unknown")

        if len(types_present) > 1:
            ctype, label = "multi", "Multi-source"
        elif "greenhouse" in types_present:
            ctype, label = "greenhouse", "Greenhouse"
        elif "lever" in types_present:
            ctype, label = "lever", "Lever"
        elif "ashby" in types_present:
            ctype, label = "ashby", "Ashby"
        else:
            ctype, label = "multi", "Multi-source"
    elif isinstance(collector, GreenhouseCollector):
        ctype, label = "greenhouse", "Greenhouse"
        sources = [source_name]
        types_present = {"greenhouse"}
    elif isinstance(collector, LeverCollector):
        ctype, label = "lever", "Lever"
        sources = [source_name]
        types_present = {"lever"}
    elif isinstance(collector, AshbyCollector):
        ctype, label = "ashby", "Ashby"
        sources = [source_name]
        types_present = {"ashby"}
    elif isinstance(collector, MockCollector):
        ctype, label = "mock", "Mock"
        sources = [source_name]
        types_present = {"mock"}
    else:
        ctype, label = "unknown", "Unknown"
        sources = [source_name]
        types_present = set()

    return {
        "type": ctype,
        "label": label,
        "sources": sources,
        "active_types": types_present,
    }
