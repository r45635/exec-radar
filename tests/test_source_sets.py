"""Tests for the source-set registry."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from packages.source_sets import (
    SourceSet,
    _REGISTRY,
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
        assert "semiconductor_exec" in names
        assert "deeptech_hardware" in names
        assert "broad_exec_ops" in names

    def test_get_known_set(self) -> None:
        """get_source_set should return a SourceSet for a known name."""
        ss = get_source_set("semiconductor_exec")
        assert isinstance(ss, SourceSet)
        assert ss.name == "semiconductor_exec"
        assert len(ss.boards) > 0

    def test_get_unknown_raises(self) -> None:
        """get_source_set should raise KeyError for an unknown name."""
        with pytest.raises(KeyError, match="Unknown source set"):
            get_source_set("nonexistent_set")

    def test_semiconductor_exec_boards(self) -> None:
        """semiconductor_exec should contain expected boards."""
        ss = get_source_set("semiconductor_exec")
        assert ss is not None
        assert "lattice" in ss.boards
        assert "tenstorrent" in ss.boards

    def test_deeptech_hardware_boards(self) -> None:
        """deeptech_hardware should contain expected boards."""
        ss = get_source_set("deeptech_hardware")
        assert ss is not None
        assert "graphcore" in ss.boards

    def test_broad_exec_ops_boards(self) -> None:
        """broad_exec_ops should contain expected boards."""
        ss = get_source_set("broad_exec_ops")
        assert ss is not None
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

    def test_semiconductor_exec_has_lever_boards(self) -> None:
        """semiconductor_exec should have Lever boards defined."""
        ss = get_source_set("semiconductor_exec")
        assert len(ss.lever_boards) > 0

    def test_semiconductor_exec_has_ashby_boards(self) -> None:
        """semiconductor_exec should have Ashby boards defined."""
        ss = get_source_set("semiconductor_exec")
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
        assert "semiconductor_exec" in _REGISTRY
