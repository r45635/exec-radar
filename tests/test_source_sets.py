"""Tests for the source-set registry."""

from __future__ import annotations

import pytest

from packages.source_sets import (
    SourceSet,
    get_source_set,
    list_source_sets,
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
        assert "groq" in ss.boards

    def test_broad_exec_ops_boards(self) -> None:
        """broad_exec_ops should contain expected boards."""
        ss = get_source_set("broad_exec_ops")
        assert ss is not None
        assert "rivian" in ss.boards

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
