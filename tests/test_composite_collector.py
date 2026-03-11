"""Tests for the CompositeCollector."""

from __future__ import annotations

import pytest

from packages.collectors.composite_collector import CompositeCollector
from packages.collectors.mock_collector import MockCollector
from packages.schemas.raw_job import RawJobPosting


class _FailingCollector(MockCollector):
    """A collector that always raises."""

    async def collect(self) -> list[RawJobPosting]:
        msg = "Simulated failure"
        raise RuntimeError(msg)

    @property
    def source_name(self) -> str:
        return "failing"


class TestCompositeCollector:
    """Tests for CompositeCollector aggregation."""

    async def test_aggregates_multiple_sources(self) -> None:
        """Should merge postings from all child collectors."""
        c = CompositeCollector([MockCollector(), MockCollector()])
        results = await c.collect()
        assert len(results) == 10  # 5 + 5

    async def test_single_child(self) -> None:
        """Should work with a single child collector."""
        c = CompositeCollector([MockCollector()])
        results = await c.collect()
        assert len(results) == 5

    async def test_source_name_combined(self) -> None:
        """Source name should combine child source names."""
        c = CompositeCollector([MockCollector(), MockCollector()])
        assert c.source_name == "mock+mock"

    async def test_empty_raises(self) -> None:
        """Empty collector list should raise ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            CompositeCollector([])

    async def test_partial_failure_continues(self) -> None:
        """If one child fails, the others should still return results."""
        c = CompositeCollector([MockCollector(), _FailingCollector()])
        results = await c.collect()
        assert len(results) == 5  # Only mock succeeds

    async def test_all_postings_are_raw(self) -> None:
        """All results should be RawJobPosting instances."""
        c = CompositeCollector([MockCollector(), MockCollector()])
        results = await c.collect()
        assert all(isinstance(r, RawJobPosting) for r in results)
