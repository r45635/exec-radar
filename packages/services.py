"""Service assembly — builds configured pipeline components.

Centralizes component construction so route handlers and the worker
stay thin and don't import concrete implementations directly.

Collector choice is controlled by the ``EXEC_RADAR_COLLECTOR`` env var:

* ``mock`` (default) — synthetic sample data.
* ``greenhouse`` — real jobs from the Greenhouse Boards API.
  Requires ``EXEC_RADAR_GREENHOUSE_BOARD`` (single token) **or**
  ``EXEC_RADAR_GREENHOUSE_BOARDS`` (comma-separated list of tokens).

Semiconductor-oriented default boards (used when no board is specified):

    lattice, tenstorrent, graphcore, lightmatter,
    sambanovasystems, cerebrassystems
"""

from __future__ import annotations

import os
from pathlib import Path

from packages.collectors.base import BaseCollector
from packages.collectors.composite_collector import CompositeCollector
from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.collectors.mock_collector import MockCollector
from packages.normalizers.base import BaseNormalizer
from packages.normalizers.simple_normalizer import SimpleNormalizer
from packages.profile_loader import load_profile
from packages.rankers.base import BaseRanker
from packages.rankers.rule_based_ranker import RuleBasedRanker
from packages.schemas.target_profile import TargetProfile

# Board token → human-readable company name
_BOARD_COMPANY_NAMES: dict[str, str] = {
    "lattice": "Lattice Semiconductor",
    "tenstorrent": "Tenstorrent",
    "graphcore": "Graphcore",
    "lightmatter": "Lightmatter",
    "sambanovasystems": "SambaNova Systems",
    "cerebrassystems": "Cerebras Systems",
}

# Default boards when EXEC_RADAR_GREENHOUSE_BOARDS is not set
_DEFAULT_SEMICONDUCTOR_BOARDS = list(_BOARD_COMPANY_NAMES.keys())


def build_collector(
    collector_name: str | None = None,
    *,
    greenhouse_board: str | None = None,
) -> BaseCollector:
    """Return a collector based on *collector_name* or env vars.

    Args:
        collector_name: ``"mock"`` or ``"greenhouse"``. Falls back to
            ``EXEC_RADAR_COLLECTOR`` env var, then ``"mock"``.
        greenhouse_board: Greenhouse board token(s). A single token or
            comma-separated list. Falls back to
            ``EXEC_RADAR_GREENHOUSE_BOARDS``, then
            ``EXEC_RADAR_GREENHOUSE_BOARD``, then the built-in
            semiconductor board list.

    Returns:
        A configured :class:`BaseCollector` instance.

    Raises:
        ValueError: If the collector name is unknown.
    """
    name = (collector_name or os.getenv("EXEC_RADAR_COLLECTOR", "mock")).lower().strip()

    if name == "mock":
        return MockCollector()

    if name == "greenhouse":
        boards_str = (
            greenhouse_board
            or os.getenv("EXEC_RADAR_GREENHOUSE_BOARDS")
            or os.getenv("EXEC_RADAR_GREENHOUSE_BOARD")
        )
        if boards_str:
            tokens = [t.strip() for t in boards_str.split(",") if t.strip()]
        else:
            tokens = list(_DEFAULT_SEMICONDUCTOR_BOARDS)

        collectors = [
            GreenhouseCollector(
                board_token=token,
                company_name=_BOARD_COMPANY_NAMES.get(token),
            )
            for token in tokens
        ]
        if len(collectors) == 1:
            return collectors[0]
        return CompositeCollector(collectors)

    msg = f"Unknown collector: {name!r}. Available: mock, greenhouse"
    raise ValueError(msg)


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
) -> tuple[BaseCollector, BaseNormalizer, BaseRanker]:
    """Build a complete set of pipeline components.

    Args:
        profile_path: Optional path to a YAML profile file.
        collector_name: Collector to use (``"mock"`` or ``"greenhouse"``).
        greenhouse_board: Greenhouse board token (if applicable).
        profile: A pre-built TargetProfile (takes precedence over path).

    Returns:
        A ``(collector, normalizer, ranker)`` tuple ready for
        :func:`packages.pipeline.run_pipeline`.
    """
    return (
        build_collector(collector_name, greenhouse_board=greenhouse_board),
        build_normalizer(),
        build_ranker(profile_path, profile=profile),
    )
