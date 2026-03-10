"""Tests for the mock collector."""

from __future__ import annotations

from packages.collectors.mock_collector import MockCollector
from packages.schemas.raw_job import RawJobPosting


class TestMockCollector:
    """Tests for MockCollector."""

    async def test_returns_postings(self) -> None:
        """Collector should return a non-empty list of RawJobPosting."""
        collector = MockCollector()
        results = await collector.collect()
        assert len(results) > 0
        assert all(isinstance(r, RawJobPosting) for r in results)

    async def test_source_name(self) -> None:
        """Source name should be 'mock'."""
        collector = MockCollector()
        assert collector.source_name == "mock"

    async def test_postings_have_titles(self) -> None:
        """Every posting should have a non-empty title."""
        collector = MockCollector()
        results = await collector.collect()
        for posting in results:
            assert posting.title.strip() != ""

    async def test_all_postings_have_source_set(self) -> None:
        """Every posting's source should match the collector's source_name."""
        collector = MockCollector()
        results = await collector.collect()
        for posting in results:
            assert posting.source == collector.source_name
