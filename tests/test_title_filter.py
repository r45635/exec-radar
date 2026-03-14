"""Tests for the executive title pre-filter."""

from __future__ import annotations

import pytest

from packages.filters import filter_executive_postings, is_executive_title
from packages.schemas.raw_job import RawJobPosting


class TestIsExecutiveTitle:
    """Test the title classification logic."""

    @pytest.mark.parametrize(
        "title",
        [
            "Chief Operating Officer",
            "COO",
            "VP of Operations",
            "Vice President Supply Chain",
            "SVP Manufacturing",
            "Senior Vice President",
            "Director of Engineering",
            "Head of Supply Chain",
            "General Manager, Business Unit",
            "Managing Director",
            "President",
            "Senior Director of Quality",
            "Executive Vice President",
            "Principal Engineer",  # principal is kept
            "Group Leader, Manufacturing",
        ],
    )
    def test_executive_titles_pass(self, title: str) -> None:
        assert is_executive_title(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineer",
            "Data Analyst",
            "Marketing Coordinator",
            "HR Specialist",
            "Intern, Operations",
            "Junior Developer",
            "Recruiting Coordinator",
            "Production Operator",
            "Lab Technician",
            "Accounts Receivable Clerk",
            "Sales Representative",
            "Administrative Assistant",
            "Mechanical Engineer",
            "Quality Analyst",
            "IT Administrator",
        ],
    )
    def test_junior_mid_titles_rejected(self, title: str) -> None:
        assert is_executive_title(title) is False

    @pytest.mark.parametrize(
        "title",
        [
            "Plant Manager",
            "Program Manager",
            "Supply Chain Manager",
            "Operations Manager",
            "Factory Manager",
        ],
    )
    def test_ambiguous_titles_kept(self, title: str) -> None:
        """Titles without clear exec/junior signals are kept."""
        assert is_executive_title(title) is True

    def test_associate_director_passes(self) -> None:
        """'Associate Director' should pass (director overrides associate)."""
        assert is_executive_title("Associate Director of Ops") is True

    def test_assistant_vice_president_passes(self) -> None:
        """'Assistant Vice President' should pass (VP overrides assistant)."""
        assert is_executive_title("Assistant Vice President") is True


class TestFilterExecutivePostings:
    """Test the batch filtering function."""

    def _make_posting(self, title: str) -> RawJobPosting:
        return RawJobPosting(
            source="test",
            source_id=title.lower().replace(" ", "-"),
            title=title,
        )

    def test_filters_irrelevant(self) -> None:
        postings = [
            self._make_posting("Chief Operating Officer"),
            self._make_posting("Software Engineer"),
            self._make_posting("VP Operations"),
            self._make_posting("Marketing Coordinator"),
            self._make_posting("Director of Finance"),
            self._make_posting("Lab Technician"),
        ]
        result = filter_executive_postings(postings)
        titles = [r.title for r in result]
        assert "Chief Operating Officer" in titles
        assert "VP Operations" in titles
        assert "Director of Finance" in titles
        assert "Software Engineer" not in titles
        assert "Marketing Coordinator" not in titles
        assert "Lab Technician" not in titles

    def test_empty_input(self) -> None:
        assert filter_executive_postings([]) == []
