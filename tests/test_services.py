"""Tests for the service assembly module."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.collectors.ashby_collector import AshbyCollector
from packages.collectors.base import BaseCollector
from packages.collectors.composite_collector import CompositeCollector
from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.collectors.lever_collector import LeverCollector
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

    def test_greenhouse_default_boards(self) -> None:
        """Greenhouse without a board token should use default semiconductor boards."""
        c = build_collector("greenhouse")
        assert isinstance(c, CompositeCollector)
        assert "samsungsemiconductor" in c.source_name
        assert "anellophotonics" in c.source_name

    def test_greenhouse_multi_boards(self) -> None:
        """Comma-separated boards should produce a CompositeCollector."""
        c = build_collector("greenhouse", greenhouse_board="lattice,tenstorrent")
        assert isinstance(c, CompositeCollector)
        assert "greenhouse:lattice" in c.source_name
        assert "greenhouse:tenstorrent" in c.source_name

    def test_greenhouse_single_board_not_composite(self) -> None:
        """A single board should return a plain GreenhouseCollector."""
        c = build_collector("greenhouse", greenhouse_board="lattice")
        assert isinstance(c, GreenhouseCollector)
        assert c.source_name == "greenhouse:lattice"

    def test_unknown_collector_raises(self) -> None:
        """Unknown collector name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown collector"):
            build_collector("nonexistent")

    def test_source_set_creates_composite(self) -> None:
        """build_collector with a source_set should produce a CompositeCollector."""
        c = build_collector("greenhouse", source_set="semiconductor_exec_core")
        assert isinstance(c, CompositeCollector)
        assert "samsungsemiconductor" in c.source_name

    def test_source_set_includes_lever_ashby(self) -> None:
        """Source sets with lever/ashby boards should include them."""
        c = build_collector("greenhouse", source_set="semiconductor_exec_core")
        assert isinstance(c, CompositeCollector)
        # Should include Greenhouse + Lever + Ashby sources
        assert "greenhouse:samsungsemiconductor" in c.source_name
        assert "lever:" in c.source_name
        assert "ashby" in c.source_name

    def test_source_set_overrides_board(self) -> None:
        """source_set should take priority over greenhouse_board."""
        c = build_collector(
            "greenhouse",
            greenhouse_board="discord",
            source_set="broad_hardware_supply_chain",
        )
        assert isinstance(c, CompositeCollector)
        assert "andurilindustries" in c.source_name

    def test_source_set_unknown_raises(self) -> None:
        """An unknown source_set should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown source set"):
            build_collector("greenhouse", source_set="unknown_set")

    def test_pipeline_with_greenhouse(self) -> None:
        """build_pipeline_components should wire Greenhouse when requested."""
        c, _n, r = build_pipeline_components(collector_name="greenhouse", greenhouse_board="test")
        assert isinstance(c, GreenhouseCollector)
        assert isinstance(r, RuleBasedRanker)

    def test_lever_single_slug(self) -> None:
        """Lever collector should be returned with a company slug."""
        c = build_collector("lever", greenhouse_board="netflix")
        assert isinstance(c, LeverCollector)
        assert c.source_name == "lever:netflix"

    def test_lever_multi_slugs(self) -> None:
        """Comma-separated slugs should produce a CompositeCollector."""
        c = build_collector("lever", greenhouse_board="netflix,twitch")
        assert isinstance(c, CompositeCollector)
        assert "lever:netflix" in c.source_name
        assert "lever:twitch" in c.source_name

    def test_lever_no_slug_raises(self) -> None:
        """Lever without a slug should raise ValueError."""
        with pytest.raises(ValueError, match="company slug"):
            build_collector("lever")

    def test_ashby_single_slug(self) -> None:
        """Ashby collector should be returned with a company slug."""
        c = build_collector("ashby", greenhouse_board="ramp")
        assert isinstance(c, AshbyCollector)
        assert c.source_name == "ashby:ramp"

    def test_ashby_multi_slugs(self) -> None:
        """Comma-separated slugs should produce a CompositeCollector."""
        c = build_collector("ashby", greenhouse_board="ramp,notion")
        assert isinstance(c, CompositeCollector)

    def test_ashby_no_slug_raises(self) -> None:
        """Ashby without a slug should raise ValueError."""
        with pytest.raises(ValueError, match="company slug"):
            build_collector("ashby")


class TestMultiCollector:
    """Tests for multi-type collector building."""

    def test_plus_separated_greenhouse_lever(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """greenhouse+lever should combine both types."""
        monkeypatch.setenv("EXEC_RADAR_LEVER_COMPANY", "netflix")
        c = build_collector("greenhouse+lever", greenhouse_board="lattice")
        assert isinstance(c, CompositeCollector)
        assert "greenhouse:lattice" in c.source_name
        assert "lever:netflix" in c.source_name

    def test_plus_separated_all_three(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """greenhouse+lever+ashby should combine all three types."""
        monkeypatch.setenv("EXEC_RADAR_LEVER_COMPANY", "netflix")
        monkeypatch.setenv("EXEC_RADAR_ASHBY_COMPANY", "ramp")
        c = build_collector("greenhouse+lever+ashby", greenhouse_board="lattice")
        assert isinstance(c, CompositeCollector)
        assert "greenhouse:lattice" in c.source_name
        assert "lever:netflix" in c.source_name
        assert "ashby" in c.source_name

    def test_all_shortcut(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """'all' should include every configured real collector type."""
        monkeypatch.setenv("EXEC_RADAR_LEVER_COMPANY", "twitch")
        monkeypatch.setenv("EXEC_RADAR_ASHBY_COMPANY", "notion")
        c = build_collector("all", greenhouse_board="tenstorrent")
        assert isinstance(c, CompositeCollector)
        assert "greenhouse:tenstorrent" in c.source_name
        assert "lever:twitch" in c.source_name
        assert "ashby" in c.source_name

    def test_all_skips_unconfigured(self) -> None:
        """'all' should skip types missing env vars (lever, ashby)."""
        c = build_collector("all", greenhouse_board="lattice")
        # Only greenhouse is configured — lever/ashby have no slug env vars
        assert "greenhouse:lattice" in c.source_name
        assert "lever:" not in c.source_name

    def test_multi_no_configured_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multi-type with nothing configured should raise ValueError."""
        monkeypatch.delenv("EXEC_RADAR_LEVER_COMPANY", raising=False)
        monkeypatch.delenv("EXEC_RADAR_ASHBY_COMPANY", raising=False)
        with pytest.raises(ValueError, match="No collectors configured"):
            build_collector("lever+ashby")

    def test_unknown_in_multi_raises(self) -> None:
        """An unknown type in a multi-spec should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown collector"):
            build_collector("greenhouse+bogus", greenhouse_board="lattice")

    def test_describe_multi_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """describe_collector should return type='multi' for mixed types."""
        from packages.services import describe_collector

        monkeypatch.setenv("EXEC_RADAR_LEVER_COMPANY", "netflix")
        c = build_collector("greenhouse+lever", greenhouse_board="lattice")
        info = describe_collector(c)
        assert info["type"] == "multi"
        assert info["label"] == "Multi-source"
        assert len(info["sources"]) >= 2
        assert "greenhouse" in info["active_types"]
        assert "lever" in info["active_types"]

    def test_source_set_multi_ats_is_multi_type(self) -> None:
        """Source set with lever/ashby should report as multi type."""
        from packages.services import describe_collector

        c = build_collector("greenhouse", source_set="semiconductor_exec_core")
        info = describe_collector(c)
        assert info["type"] == "multi"
        assert "greenhouse" in info["active_types"]
        assert "lever" in info["active_types"]
        assert "ashby" in info["active_types"]
