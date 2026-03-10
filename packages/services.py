"""Service assembly — builds configured pipeline components.

Centralizes component construction so route handlers and the worker
stay thin and don't import concrete implementations directly.

Collector choice is controlled by the ``EXEC_RADAR_COLLECTOR`` env var:

* ``mock`` (default) — synthetic sample data.
* ``greenhouse`` — real jobs from the Greenhouse Boards API.
  Requires ``EXEC_RADAR_GREENHOUSE_BOARD`` (e.g. ``discord``).
"""

from __future__ import annotations

import os
from pathlib import Path

from packages.collectors.base import BaseCollector
from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.collectors.mock_collector import MockCollector
from packages.normalizers.base import BaseNormalizer
from packages.normalizers.simple_normalizer import SimpleNormalizer
from packages.profile_loader import load_profile
from packages.rankers.base import BaseRanker
from packages.rankers.rule_based_ranker import RuleBasedRanker


def build_collector(
    collector_name: str | None = None,
    *,
    greenhouse_board: str | None = None,
) -> BaseCollector:
    """Return a collector based on *collector_name* or env vars.

    Args:
        collector_name: ``"mock"`` or ``"greenhouse"``. Falls back to
            ``EXEC_RADAR_COLLECTOR`` env var, then ``"mock"``.
        greenhouse_board: Greenhouse board token. Falls back to
            ``EXEC_RADAR_GREENHOUSE_BOARD`` env var.

    Returns:
        A configured :class:`BaseCollector` instance.

    Raises:
        ValueError: If the collector name is unknown, or Greenhouse is
            selected but no board token is provided.
    """
    name = (collector_name or os.getenv("EXEC_RADAR_COLLECTOR", "mock")).lower().strip()

    if name == "mock":
        return MockCollector()

    if name == "greenhouse":
        board = greenhouse_board or os.getenv("EXEC_RADAR_GREENHOUSE_BOARD")
        if not board:
            msg = (
                "Greenhouse collector requires a board token. "
                "Set EXEC_RADAR_GREENHOUSE_BOARD or pass greenhouse_board=."
            )
            raise ValueError(msg)
        return GreenhouseCollector(board_token=board)

    msg = f"Unknown collector: {name!r}. Available: mock, greenhouse"
    raise ValueError(msg)


def build_normalizer() -> BaseNormalizer:
    """Return the default normalizer implementation."""
    return SimpleNormalizer()


def build_ranker(profile_path: str | Path | None = None) -> BaseRanker:
    """Return a ranker loaded with the given profile (or defaults).

    Args:
        profile_path: Optional path to a YAML profile file.
    """
    profile = load_profile(profile_path)
    return RuleBasedRanker(profile=profile)


def build_pipeline_components(
    profile_path: str | Path | None = None,
    collector_name: str | None = None,
    *,
    greenhouse_board: str | None = None,
) -> tuple[BaseCollector, BaseNormalizer, BaseRanker]:
    """Build a complete set of pipeline components.

    Args:
        profile_path: Optional path to a YAML profile file.
        collector_name: Collector to use (``"mock"`` or ``"greenhouse"``).
        greenhouse_board: Greenhouse board token (if applicable).

    Returns:
        A ``(collector, normalizer, ranker)`` tuple ready for
        :func:`packages.pipeline.run_pipeline`.
    """
    return (
        build_collector(collector_name, greenhouse_board=greenhouse_board),
        build_normalizer(),
        build_ranker(profile_path),
    )
