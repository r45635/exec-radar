"""Named source sets — curated board lists for different use cases.

Each source set defines boards/slugs across multiple ATS platforms:
Greenhouse, Lever, and Ashby.  Source sets can be referenced by name
from a :class:`TargetProfile` or via the
``EXEC_RADAR_SOURCE_SET`` environment variable.

Loading order:
1. ``sources.yaml`` in the project root (preferred).
2. Hardcoded fallback definitions below.

The YAML file is validated at load time; malformed entries are skipped
with a warning.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceSet:
    """A named collection of job boards across ATS platforms."""

    name: str
    description: str
    boards: dict[str, str] = field(default_factory=dict)
    """Greenhouse: board_token → company display name."""
    lever_boards: dict[str, str] = field(default_factory=dict)
    """Lever: company_slug → company display name."""
    ashby_boards: dict[str, str] = field(default_factory=dict)
    """Ashby: company_slug → company display name."""


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_YAML_PATH = _PROJECT_ROOT / "sources.yaml"


def _validate_source_set(entry: dict[str, Any], idx: int) -> SourceSet | None:
    """Validate a single YAML entry and return a SourceSet or None."""
    name = entry.get("name")
    if not name or not isinstance(name, str):
        logger.warning("sources.yaml entry %d: missing or invalid 'name', skipping", idx)
        return None

    description = entry.get("description", "")
    if not isinstance(description, str):
        description = str(description)

    def _validate_board_dict(key: str) -> dict[str, str]:
        raw = entry.get(key) or {}
        if not isinstance(raw, dict):
            logger.warning("sources.yaml '%s'.%s: expected dict, got %s", name, key, type(raw).__name__)
            return {}
        result: dict[str, str] = {}
        for k, v in raw.items():
            if not isinstance(k, str) or not k.strip():
                continue
            result[str(k).strip()] = str(v or k).strip()
        return result

    boards = _validate_board_dict("boards")
    lever_boards = _validate_board_dict("lever_boards")
    ashby_boards = _validate_board_dict("ashby_boards")

    if not boards and not lever_boards and not ashby_boards:
        logger.warning("sources.yaml '%s': no boards defined, skipping", name)
        return None

    return SourceSet(
        name=name.strip(),
        description=description.strip(),
        boards=boards,
        lever_boards=lever_boards,
        ashby_boards=ashby_boards,
    )


def load_source_sets_from_yaml(
    path: str | Path | None = None,
) -> dict[str, SourceSet]:
    """Load source sets from a YAML file.

    Returns:
        Dict mapping source-set name → SourceSet.  Empty dict if the
        file doesn't exist or has no valid entries.
    """
    yaml_path = Path(path) if path else _DEFAULT_YAML_PATH
    env_override = os.getenv("EXEC_RADAR_SOURCES_YAML")
    if env_override:
        yaml_path = Path(env_override)

    if not yaml_path.is_file():
        return {}

    raw: Any = yaml.safe_load(yaml_path.read_text())
    if not isinstance(raw, list):
        logger.warning("sources.yaml: expected a list, got %s", type(raw).__name__)
        return {}

    registry: dict[str, SourceSet] = {}
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            logger.warning("sources.yaml entry %d: expected dict, skipping", idx)
            continue
        ss = _validate_source_set(entry, idx)
        if ss:
            registry[ss.name] = ss

    return registry


# ---------------------------------------------------------------------------
# Registry (YAML → hardcoded fallback)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, SourceSet] = {}


def _register(ss: SourceSet) -> SourceSet:
    _REGISTRY[ss.name] = ss
    return ss


def _load_registry() -> None:
    """Populate registry: YAML first, hardcoded fallback if YAML absent."""
    yaml_sets = load_source_sets_from_yaml()
    if yaml_sets:
        _REGISTRY.clear()
        _REGISTRY.update(yaml_sets)
        return

    # Hardcoded fallback (backward compatibility)
    _REGISTRY.clear()

    _register(SourceSet(
        name="semiconductor_exec",
        description=(
            "Semiconductor companies with executive operations, supply-chain, "
            "and industrialization roles (IDM, fabless, foundry, OSAT)."
        ),
        boards={
            "lattice": "Lattice Semiconductor",
            "tenstorrent": "Tenstorrent",
            "allegro": "Allegro Microsystems",
            "lightmatter": "Lightmatter",
            "cerebrassystems": "Cerebras Systems",
            "sambanovasystems": "SambaNova Systems",
            "luminar": "Luminar Technologies",
            "atomicmachines": "Atomic Machines",
            "markforged": "Markforged",
            "samsara": "Samsara",
            "verkada": "Verkada",
            "astranis": "Astranis",
        },
        lever_boards={
            "rigetti": "Rigetti Computing",
            "aeva": "Aeva Technologies",
        },
        ashby_boards={
            "ramp": "Ramp",
            "cohere": "Cohere",
        },
    ))

    _register(SourceSet(
        name="deeptech_hardware",
        description=(
            "AI-hardware, photonics, quantum, and advanced computing "
            "companies with executive and operations roles."
        ),
        boards={
            "lightmatter": "Lightmatter",
            "cerebrassystems": "Cerebras Systems",
            "tenstorrent": "Tenstorrent",
            "sambanovasystems": "SambaNova Systems",
            "graphcore": "Graphcore",
            "matx": "MATX",
            "scaleai": "Scale AI",
            "formlabs": "Formlabs",
        },
        lever_boards={
            "rigetti": "Rigetti Computing",
            "hermeus": "Hermeus",
        },
        ashby_boards={
            "notion": "Notion",
            "linear": "Linear",
        },
    ))

    _register(SourceSet(
        name="broad_exec_ops",
        description=(
            "Large companies across semiconductor, automotive, aerospace, "
            "and industrial manufacturing with executive-level postings."
        ),
        boards={
            "lattice": "Lattice Semiconductor",
            "tenstorrent": "Tenstorrent",
            "allegro": "Allegro Microsystems",
            "lucidmotors": "Lucid Motors",
            "relativity": "Relativity Space",
            "andurilindustries": "Anduril Industries",
            "archer": "Archer Aviation",
            "rocketlab": "Rocket Lab",
            "luminar": "Luminar Technologies",
            "momentus": "Momentus",
        },
        lever_boards={
            "aeva": "Aeva Technologies",
            "hermeus": "Hermeus",
        },
        ashby_boards={
            "ramp": "Ramp",
            "cohere": "Cohere",
        },
    ))


# Load on import
_load_registry()


def reload_registry(yaml_path: str | Path | None = None) -> int:
    """Re-load source sets from YAML (or fallback). Returns count loaded."""
    if yaml_path:
        yaml_sets = load_source_sets_from_yaml(yaml_path)
        if yaml_sets:
            _REGISTRY.clear()
            _REGISTRY.update(yaml_sets)
            return len(_REGISTRY)
    _load_registry()
    return len(_REGISTRY)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_source_set(name: str) -> SourceSet:
    """Return a source set by name.

    Raises:
        KeyError: If no source set with *name* exists.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY))
        raise KeyError(
            f"Unknown source set {name!r}. Available: {available}"
        ) from None


def list_source_sets() -> list[SourceSet]:
    """Return all registered source sets (sorted by name)."""
    return sorted(_REGISTRY.values(), key=lambda s: s.name)


def source_set_names() -> list[str]:
    """Return sorted list of registered source-set names."""
    return sorted(_REGISTRY)
