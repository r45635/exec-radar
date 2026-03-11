"""Tests for title-family normalization."""

from __future__ import annotations

import pytest

from packages.normalizers.title_families import (
    NON_OPS_CSUITE,
    OPERATIONS_FAMILIES,
    resolve_title_family,
)


class TestResolveTitleFamily:
    """Verify title → family mapping."""

    @pytest.mark.parametrize(
        ("title", "expected_family"),
        [
            ("Chief Operating Officer", "COO"),
            ("COO", "COO"),
            ("Chief Executive Officer", "CEO"),
            ("CEO", "CEO"),
            ("Chief Financial Officer", "CFO"),
            ("Chief Technology Officer", "CTO"),
            ("Chief Marketing Officer", "CMO"),
            ("VP of Operations", "VP_OPERATIONS"),
            ("Senior Vice President of Operations", "VP_OPERATIONS"),
            ("SVP Operations", "VP_OPERATIONS"),
            ("Vice President Manufacturing", "VP_MANUFACTURING"),
            ("VP Supply Chain", "VP_SUPPLY_CHAIN"),
            ("VP of Engineering", "VP_ENGINEERING"),
            ("VP Quality", "VP_QUALITY"),
            ("Head of Operations", "HEAD_OPERATIONS"),
            ("Director of Operations", "HEAD_OPERATIONS"),
            ("Head of Manufacturing", "HEAD_MANUFACTURING"),
            ("Director of Supply Chain", "HEAD_SUPPLY_CHAIN"),
            ("Head of Quality", "HEAD_QUALITY"),
            ("Head of Business Transformation", "HEAD_TRANSFORMATION"),
            ("Plant Director", "PLANT_DIRECTOR"),
            ("Site Manager", "PLANT_DIRECTOR"),
            ("Factory Director", "PLANT_DIRECTOR"),
            ("General Manager Operations", "GM_OPERATIONS"),
        ],
    )
    def test_known_titles(self, title: str, expected_family: str) -> None:
        assert resolve_title_family(title) == expected_family

    def test_unknown_title_returns_none(self) -> None:
        assert resolve_title_family("Senior Barista") is None

    def test_case_insensitive(self) -> None:
        assert resolve_title_family("chief operating officer") == "COO"
        assert resolve_title_family("CHIEF OPERATING OFFICER") == "COO"


class TestFamilySets:
    """Verify the family classification sets."""

    def test_operations_families_non_empty(self) -> None:
        assert len(OPERATIONS_FAMILIES) > 0

    def test_non_ops_csuite_non_empty(self) -> None:
        assert len(NON_OPS_CSUITE) > 0

    def test_no_overlap(self) -> None:
        assert OPERATIONS_FAMILIES & NON_OPS_CSUITE == set()
