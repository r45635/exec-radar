"""Profile loader — reads a TargetProfile from a YAML file or returns defaults."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from packages.schemas.target_profile import TargetProfile

logger = logging.getLogger(__name__)


def load_profile(path: str | Path | None = None) -> TargetProfile:
    """Load a :class:`TargetProfile` from a YAML file.

    If *path* is ``None`` or the file does not exist, the built-in
    default profile is returned.  The loaded data is validated through
    Pydantic, so invalid values will raise :class:`ValidationError`.

    Args:
        path: Filesystem path to a YAML profile file, or ``None``.

    Returns:
        A validated :class:`TargetProfile` instance.
    """
    if path is None:
        return TargetProfile()

    file_path = Path(path)
    if not file_path.is_file():
        logger.warning("Profile file not found: %s — using defaults", file_path)
        return TargetProfile()

    raw: dict[str, Any] = yaml.safe_load(file_path.read_text()) or {}
    return TargetProfile(**raw)
