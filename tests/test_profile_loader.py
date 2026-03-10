"""Tests for the profile loader utility."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.profile_loader import load_profile
from packages.schemas.target_profile import TargetProfile


class TestLoadProfile:
    """Tests for load_profile()."""

    def test_none_returns_default(self) -> None:
        """Passing None should return the built-in default profile."""
        profile = load_profile(None)
        assert profile == TargetProfile()

    def test_missing_file_returns_default(self, tmp_path: Path) -> None:
        """A non-existent path should fall back to the default profile."""
        profile = load_profile(tmp_path / "does_not_exist.yaml")
        assert profile == TargetProfile()

    def test_valid_yaml_file(self, tmp_path: Path) -> None:
        """A valid YAML file should produce a customized profile."""
        p = tmp_path / "profile.yaml"
        p.write_text("target_titles:\n  - cto\n  - vp engineering\nweight_title: 0.5\n")
        profile = load_profile(p)
        assert "cto" in profile.target_titles
        assert profile.weight_title == 0.5

    def test_empty_yaml_returns_default(self, tmp_path: Path) -> None:
        """An empty YAML file should return the default profile."""
        p = tmp_path / "empty.yaml"
        p.write_text("")
        profile = load_profile(p)
        assert profile == TargetProfile()

    def test_invalid_value_raises(self, tmp_path: Path) -> None:
        """A YAML file with invalid values should raise ValidationError."""
        p = tmp_path / "bad.yaml"
        p.write_text("weight_title: 2.0\n")  # exceeds max 1.0
        with pytest.raises(ValidationError):
            load_profile(p)

    def test_string_path_accepted(self, tmp_path: Path) -> None:
        """The function should accept a plain string path."""
        p = tmp_path / "profile.yaml"
        p.write_text("weight_seniority: 0.4\n")
        profile = load_profile(str(p))
        assert profile.weight_seniority == 0.4

    def test_partial_override(self, tmp_path: Path) -> None:
        """Fields not in the YAML should keep their defaults."""
        p = tmp_path / "partial.yaml"
        p.write_text("excluded_titles:\n  - intern\n")
        profile = load_profile(p)
        assert "intern" in profile.excluded_titles
        assert len(profile.target_titles) > 0  # defaults preserved
