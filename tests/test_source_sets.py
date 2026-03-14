"""Tests for the source-set registry."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from packages.source_sets import (
    _REGISTRY,
    SourceEntry,
    SourceSet,
    _make_source_set,
    describe_all_source_sets,
    describe_source_set,
    get_source_set,
    list_source_sets,
    load_source_sets_from_yaml,
    reload_registry,
    source_set_names,
)


class TestSourceSetRegistry:
    """Verify the built-in source sets and registry API."""

    def test_list_returns_list(self) -> None:
        """list_source_sets should return a list of SourceSet objects."""
        result = list_source_sets()
        assert isinstance(result, list)
        assert len(result) >= 3
        assert all(isinstance(ss, SourceSet) for ss in result)

    def test_names_returns_sorted_list(self) -> None:
        """source_set_names should return a sorted list of strings."""
        names = source_set_names()
        assert isinstance(names, list)
        assert names == sorted(names)
        assert "semiconductor_exec_core" in names
        assert "photonics_mems_ops" in names
        assert "broad_hardware_supply_chain" in names

    def test_get_known_set(self) -> None:
        """get_source_set should return a SourceSet for a known name."""
        ss = get_source_set("semiconductor_exec_core")
        assert isinstance(ss, SourceSet)
        assert ss.name == "semiconductor_exec_core"
        assert len(ss.boards) > 0

    def test_get_unknown_raises(self) -> None:
        """get_source_set should raise KeyError for an unknown name."""
        with pytest.raises(KeyError, match="Unknown source set"):
            get_source_set("nonexistent_set")

    def test_semiconductor_exec_core_boards(self) -> None:
        """semiconductor_exec_core should contain expected boards."""
        ss = get_source_set("semiconductor_exec_core")
        assert "samsungsemiconductor" in ss.boards
        assert "anellophotonics" in ss.boards
        assert "andurilindustries" in ss.boards

    def test_photonics_mems_ops_boards(self) -> None:
        """photonics_mems_ops should contain expected boards."""
        ss = get_source_set("photonics_mems_ops")
        assert "anellophotonics" in ss.boards

    def test_broad_hardware_supply_chain_boards(self) -> None:
        """broad_hardware_supply_chain should contain expected boards."""
        ss = get_source_set("broad_hardware_supply_chain")
        assert "andurilindustries" in ss.boards

    def test_source_set_has_description(self) -> None:
        """Every source set should have a non-empty description."""
        for ss in list_source_sets():
            assert ss.description, f"{ss.name} has no description"

    def test_boards_have_labels(self) -> None:
        """Every board in each source set should have a label."""
        for ss in list_source_sets():
            for board, label in ss.boards.items():
                assert board, f"{ss.name} has an empty board key"
                assert label, f"{ss.name} board {board} has no label"

    def test_semiconductor_exec_core_has_lever_boards(self) -> None:
        """semiconductor_exec_core should have Lever boards defined."""
        ss = get_source_set("semiconductor_exec_core")
        assert len(ss.lever_boards) > 0

    def test_semiconductor_exec_core_has_ashby_boards(self) -> None:
        """semiconductor_exec_core should have Ashby boards defined."""
        ss = get_source_set("semiconductor_exec_core")
        assert len(ss.ashby_boards) > 0

    def test_lever_ashby_boards_have_labels(self) -> None:
        """Every lever/ashby board in each source set should have a label."""
        for ss in list_source_sets():
            for slug, label in ss.lever_boards.items():
                assert slug, f"{ss.name} has an empty lever slug"
                assert label, f"{ss.name} lever {slug} has no label"
            for slug, label in ss.ashby_boards.items():
                assert slug, f"{ss.name} has an empty ashby slug"
                assert label, f"{ss.name} ashby {slug} has no label"

    def test_no_noisy_software_companies_in_defaults(self) -> None:
        """Default sets should not include noisy software-centric boards."""
        noisy = {"ramp", "notion", "linear", "cohere", "samsara", "verkada", "scaleai"}
        for ss in list_source_sets():
            all_slugs = set(ss.boards) | set(ss.lever_boards) | set(ss.ashby_boards)
            overlap = all_slugs & noisy
            assert not overlap, f"{ss.name} contains noisy boards: {overlap}"


class TestSourceSetProperties:
    """Verify the enriched SourceSet properties."""

    def test_total_sources(self) -> None:
        ss = get_source_set("semiconductor_exec_core")
        expected = len(ss.boards) + len(ss.lever_boards) + len(ss.ashby_boards)
        assert ss.total_sources == expected
        assert ss.total_sources > 0

    def test_source_count_by_ats(self) -> None:
        ss = get_source_set("semiconductor_exec_core")
        by_ats = ss.source_count_by_ats
        assert by_ats["greenhouse"] == len(ss.boards)
        assert by_ats["lever"] == len(ss.lever_boards)
        assert by_ats["ashby"] == len(ss.ashby_boards)

    def test_all_companies(self) -> None:
        ss = get_source_set("semiconductor_exec_core")
        companies = ss.all_companies
        assert isinstance(companies, list)
        assert len(companies) > 0
        assert companies == sorted(companies)

    def test_all_focus_tags(self) -> None:
        ss = get_source_set("semiconductor_exec_core")
        tags = ss.all_focus_tags
        assert isinstance(tags, set)
        # YAML enriched entries should have focus_tags
        assert len(tags) > 0

    def test_describe(self) -> None:
        ss = get_source_set("semiconductor_exec_core")
        desc = ss.describe()
        assert desc["name"] == "semiconductor_exec_core"
        assert "total_sources" in desc
        assert "by_ats" in desc
        assert "companies" in desc
        assert "focus_tags" in desc
        assert "sources" in desc
        assert isinstance(desc["sources"], list)


class TestSourceEntry:
    """Tests for the SourceEntry dataclass."""

    def test_to_dict(self) -> None:
        entry = SourceEntry(
            display_name="Test Co",
            ats_type="greenhouse",
            slug="testco",
            priority=2,
            focus_tags=("chip", "semi"),
            noise_risk="low",
            regions=("US",),
            notes="A test",
        )
        d = entry.to_dict()
        assert d["display_name"] == "Test Co"
        assert d["ats_type"] == "greenhouse"
        assert d["priority"] == 2
        assert d["focus_tags"] == ["chip", "semi"]
        assert d["noise_risk"] == "low"
        assert d["regions"] == ["US"]

    def test_defaults(self) -> None:
        entry = SourceEntry(
            display_name="X", ats_type="lever", slug="x",
        )
        assert entry.priority == 5
        assert entry.focus_tags == ()
        assert entry.noise_risk == "medium"
        assert entry.regions == ()
        assert entry.notes == ""


class TestDescribeHelpers:
    """Tests for describe_source_set / describe_all_source_sets."""

    def test_describe_source_set(self) -> None:
        desc = describe_source_set("semiconductor_exec_core")
        assert desc["name"] == "semiconductor_exec_core"
        assert desc["total_sources"] > 0

    def test_describe_source_set_unknown(self) -> None:
        with pytest.raises(KeyError):
            describe_source_set("nonexistent")

    def test_describe_all(self) -> None:
        all_desc = describe_all_source_sets()
        assert isinstance(all_desc, list)
        assert len(all_desc) >= 3
        names = {d["name"] for d in all_desc}
        assert "semiconductor_exec_core" in names
        assert "photonics_mems_ops" in names
        assert "broad_hardware_supply_chain" in names


class TestMakeSourceSet:
    """Tests for _make_source_set helper."""

    def test_auto_meta_generation(self) -> None:
        ss = _make_source_set(
            "test", "desc",
            boards={"a": "A Co"},
            lever_boards={"b": "B Co"},
            ashby_boards={"c": "C Co"},
        )
        assert ss.total_sources == 3
        assert "greenhouse:a" in ss.sources_meta
        assert "lever:b" in ss.sources_meta
        assert "ashby:c" in ss.sources_meta
        assert ss.sources_meta["greenhouse:a"].display_name == "A Co"


class TestYAMLLoader:
    """Tests for YAML-based source set loading."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        """A valid YAML file should be parsed into SourceSets."""
        yaml_content = textwrap.dedent("""\
        - name: test_set
          description: "Test source set"
          boards:
            testboard: "Test Company"
          lever_boards:
            testlever: "Lever Company"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        assert "test_set" in result
        ss = result["test_set"]
        assert ss.name == "test_set"
        assert ss.boards == {"testboard": "Test Company"}
        assert ss.lever_boards == {"testlever": "Lever Company"}
        # Simple entries should auto-generate sources_meta
        assert "greenhouse:testboard" in ss.sources_meta
        assert ss.sources_meta["greenhouse:testboard"].display_name == "Test Company"

    def test_load_enriched_yaml(self, tmp_path: Path) -> None:
        """Enriched YAML source entries should parse metadata."""
        yaml_content = textwrap.dedent("""\
        - name: enriched_set
          description: "Enriched test"
          boards:
            myboard:
              display_name: "My Board Inc"
              priority: 2
              focus_tags: [chip, semi]
              noise_risk: low
              regions: [US, EU]
              notes: "A great board"
          lever_boards:
            mylever: "Simple Lever"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        assert "enriched_set" in result
        ss = result["enriched_set"]
        # boards dict should have slug → display_name
        assert ss.boards == {"myboard": "My Board Inc"}
        assert ss.lever_boards == {"mylever": "Simple Lever"}
        # sources_meta should have enriched entry
        meta = ss.sources_meta["greenhouse:myboard"]
        assert meta.priority == 2
        assert meta.focus_tags == ("chip", "semi")
        assert meta.noise_risk == "low"
        assert meta.regions == ("US", "EU")
        assert meta.notes == "A great board"
        # Simple lever entry should have defaults
        lever_meta = ss.sources_meta["lever:mylever"]
        assert lever_meta.priority == 5
        assert lever_meta.noise_risk == "medium"

    def test_load_mixed_format(self, tmp_path: Path) -> None:
        """A mix of simple and enriched entries should both parse correctly."""
        yaml_content = textwrap.dedent("""\
        - name: mixed_set
          description: "Mixed format"
          boards:
            simple_board: "Simple Co"
            enriched_board:
              display_name: "Enriched Co"
              priority: 1
              focus_tags: [ai]
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        ss = result["mixed_set"]
        assert ss.boards == {"simple_board": "Simple Co", "enriched_board": "Enriched Co"}
        assert ss.sources_meta["greenhouse:simple_board"].priority == 5  # default
        assert ss.sources_meta["greenhouse:enriched_board"].priority == 1

    def test_invalid_priority_clamped(self, tmp_path: Path) -> None:
        """Invalid priority values should be clamped to default."""
        yaml_content = textwrap.dedent("""\
        - name: bad_priority
          description: "Bad prio"
          boards:
            b1:
              display_name: "Board"
              priority: 99
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        assert result["bad_priority"].sources_meta["greenhouse:b1"].priority == 5

    def test_text_priority_mapped(self, tmp_path: Path) -> None:
        """Text priorities (high/medium/low) should map to int values."""
        yaml_content = textwrap.dedent("""\
        - name: text_prio
          description: "Text priority"
          boards:
            b_high:
              display_name: "High"
              priority: high
            b_med:
              display_name: "Med"
              priority: medium
            b_low:
              display_name: "Low"
              priority: low
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        meta = result["text_prio"].sources_meta
        assert meta["greenhouse:b_high"].priority == 9
        assert meta["greenhouse:b_med"].priority == 5
        assert meta["greenhouse:b_low"].priority == 2

    def test_invalid_noise_risk_defaulted(self, tmp_path: Path) -> None:
        """Invalid noise_risk should default to 'medium'."""
        yaml_content = textwrap.dedent("""\
        - name: bad_noise
          description: "Bad noise"
          boards:
            b1:
              display_name: "Board"
              noise_risk: "extreme"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        assert result["bad_noise"].sources_meta["greenhouse:b1"].noise_risk == "medium"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Missing YAML should return empty dict."""
        result = load_source_sets_from_yaml(tmp_path / "nope.yaml")
        assert result == {}

    def test_load_invalid_yaml_not_list(self, tmp_path: Path) -> None:
        """A YAML file that isn't a list should return empty dict."""
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text("key: value\n")
        result = load_source_sets_from_yaml(yaml_file)
        assert result == {}

    def test_load_skips_entries_without_name(self, tmp_path: Path) -> None:
        """Entries without a name should be skipped."""
        yaml_content = textwrap.dedent("""\
        - description: "No name"
          boards:
            b: "C"
        - name: valid
          description: "Valid"
          boards:
            a: "A"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        assert "valid" in result
        assert len(result) == 1

    def test_load_skips_entries_without_boards(self, tmp_path: Path) -> None:
        """Entries with no boards at all should be skipped."""
        yaml_content = textwrap.dedent("""\
        - name: empty_boards
          description: "No boards"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        assert result == {}

    def test_reload_from_yaml(self, tmp_path: Path) -> None:
        """reload_registry should load from YAML and update registry."""
        yaml_content = textwrap.dedent("""\
        - name: reload_test
          description: "Reload test"
          boards:
            r1: "R1"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        count = reload_registry(yaml_file)
        assert count == 1
        assert "reload_test" in _REGISTRY
        # Restore original
        reload_registry()
        assert "semiconductor_exec_core" in _REGISTRY


class TestBackwardCompatibility:
    """Ensure backward compat with legacy simple-format source sets."""

    def test_simple_yaml_still_works(self, tmp_path: Path) -> None:
        """Pure simple-format YAML (no enriched entries) still loads."""
        yaml_content = textwrap.dedent("""\
        - name: legacy_set
          description: "Old-style definition"
          boards:
            boardA: "Company A"
            boardB: "Company B"
          lever_boards:
            leverA: "Lever A"
          ashby_boards:
            ashbyA: "Ashby A"
        """)
        yaml_file = tmp_path / "sources.yaml"
        yaml_file.write_text(yaml_content)
        result = load_source_sets_from_yaml(yaml_file)
        ss = result["legacy_set"]
        assert ss.boards == {"boardA": "Company A", "boardB": "Company B"}
        assert ss.lever_boards == {"leverA": "Lever A"}
        assert ss.ashby_boards == {"ashbyA": "Ashby A"}
        assert ss.total_sources == 4
        assert ss.source_count_by_ats == {"greenhouse": 2, "lever": 1, "ashby": 1}

    def test_boards_dict_unchanged_for_services(self) -> None:
        """boards / lever_boards / ashby_boards are dict[str, str] for services.py."""
        for ss in list_source_sets():
            for token, name in ss.boards.items():
                assert isinstance(token, str)
                assert isinstance(name, str)
            for slug, name in ss.lever_boards.items():
                assert isinstance(slug, str)
                assert isinstance(name, str)
            for slug, name in ss.ashby_boards.items():
                assert isinstance(slug, str)
                assert isinstance(name, str)
