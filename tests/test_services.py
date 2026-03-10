"""Tests for the service assembly module."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.collectors.base import BaseCollector
from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.collectors.mock_collector import MockCollector
from packages.normalizers.base import BaseNormalizer
from packages.rankers.base import BaseRanker
from packages.rankers.rule_based_ranker import RuleBasedRanker
from packages.schemas.target_profile import TargetProfile
from packages.services import (
    build_collector,
    build_normalizer,
    build_pipeline_components,
    build_ranker,
)


class TestBuildPipelineComponents:
    """Tests for the factory functions."""

    def test_returns_three_components(self) -> None:
        """build_pipeline_components should return collector, normalizer, ranker."""
        collector, normalizer, ranker = build_pipeline_components()
        assert isinstance(collector, BaseCollector)
        assert isinstance(normalizer, BaseNormalizer)
        assert isinstance(ranker, BaseRanker)

    def test_default_profile(self) -> None:
        """Without a profile path, the ranker should use the default profile."""
        _, _, ranker = build_pipeline_components()
        assert isinstance(ranker, RuleBasedRanker)
        assert ranker.profile == TargetProfile()

    def test_custom_profile_path(self, tmp_path: Path) -> None:
        """A valid profile path should produce a customized ranker."""
        profile_file = tmp_path / "profile.yaml"
        profile_file.write_text("target_titles:\n  - data scientist\n")
        _, _, ranker = build_pipeline_components(profile_path=profile_file)
        assert isinstance(ranker, RuleBasedRanker)
        assert "data scientist" in ranker.profile.target_titles

    def test_build_collector_returns_base(self) -> None:
        """build_collector should return a BaseCollector instance."""
        assert isinstance(build_collector(), BaseCollector)

    def test_build_normalizer_returns_base(self) -> None:
        """build_normalizer should return a BaseNormalizer instance."""
        assert isinstance(build_normalizer(), BaseNormalizer)

    def test_build_ranker_default(self) -> None:
        """build_ranker without a path should use defaults."""
        ranker = build_ranker()
        assert isinstance(ranker, RuleBasedRanker)
        assert ranker.profile == TargetProfile()


class TestBuildCollectorSelector:
    """Tests for collector selection via build_collector."""

    def test_default_is_mock(self) -> None:
        """Default collector should be MockCollector."""
        c = build_collector()
        assert isinstance(c, MockCollector)

    def test_explicit_mock(self) -> None:
        """Explicit 'mock' should return MockCollector."""
        c = build_collector("mock")
        assert isinstance(c, MockCollector)

    def test_greenhouse_with_board(self) -> None:
        """Greenhouse collector should be returned with a board token."""
        c = build_collector("greenhouse", greenhouse_board="discord")
        assert isinstance(c, GreenhouseCollector)
        assert c.source_name == "greenhouse:discord"

    def test_greenhouse_missing_board_raises(self) -> None:
        """Greenhouse without a board token should raise ValueError."""
        with pytest.raises(ValueError, match="board token"):
            build_collector("greenhouse")

    def test_unknown_collector_raises(self) -> None:
        """Unknown collector name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown collector"):
            build_collector("nonexistent")

    def test_pipeline_with_greenhouse(self) -> None:
        """build_pipeline_components should wire Greenhouse when requested."""
        c, _n, r = build_pipeline_components(collector_name="greenhouse", greenhouse_board="test")
        assert isinstance(c, GreenhouseCollector)
        assert isinstance(r, RuleBasedRanker)
