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

Source entries support two formats:

* **Simple**: ``board_token: "Company Name"``
* **Enriched**: ``board_token: {display_name: ..., priority: ..., ...}``

Enriched entries may include ``priority``, ``focus_tags``,
``noise_risk``, ``regions``, and ``notes``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

_VALID_NOISE_RISK = frozenset({"low", "medium", "high"})

_PRIORITY_TEXT_TO_INT: dict[str, int] = {
    "high": 9,
    "medium": 5,
    "low": 2,
}


def _coerce_priority(raw: Any) -> int:
    """Convert a priority value (int 1-10 or text high/medium/low) to int."""
    if isinstance(raw, int) and 1 <= raw <= 10:
        return raw
    if isinstance(raw, str):
        return _PRIORITY_TEXT_TO_INT.get(raw.strip().lower(), 5)
    return 5


@dataclass(frozen=True)
class SourceEntry:
    """Metadata for a single board/slug in a source set."""

    display_name: str
    ats_type: str  # "greenhouse", "lever", or "ashby"
    slug: str
    priority: int = 5
    focus_tags: tuple[str, ...] = ()
    noise_risk: str = "medium"
    regions: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (for API / template use)."""
        return {
            "display_name": self.display_name,
            "ats_type": self.ats_type,
            "slug": self.slug,
            "priority": self.priority,
            "focus_tags": list(self.focus_tags),
            "noise_risk": self.noise_risk,
            "regions": list(self.regions),
            "notes": self.notes,
        }


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
    sources_meta: dict[str, SourceEntry] = field(default_factory=dict)
    """Enriched source metadata keyed by ``ats_type:slug``."""

    # -- Convenience properties -------------------------------------------

    @property
    def total_sources(self) -> int:
        return len(self.boards) + len(self.lever_boards) + len(self.ashby_boards)

    @property
    def source_count_by_ats(self) -> dict[str, int]:
        return {
            "greenhouse": len(self.boards),
            "lever": len(self.lever_boards),
            "ashby": len(self.ashby_boards),
        }

    @property
    def all_companies(self) -> list[str]:
        """All display names across every ATS, sorted."""
        return sorted(
            set(self.boards.values())
            | set(self.lever_boards.values())
            | set(self.ashby_boards.values())
        )

    @property
    def all_focus_tags(self) -> set[str]:
        tags: set[str] = set()
        for entry in self.sources_meta.values():
            tags.update(entry.focus_tags)
        return tags

    def describe(self) -> dict[str, Any]:
        """Return a summary dict suitable for dashboard rendering."""
        return {
            "name": self.name,
            "description": self.description,
            "total_sources": self.total_sources,
            "by_ats": self.source_count_by_ats,
            "companies": self.all_companies,
            "focus_tags": sorted(self.all_focus_tags),
            "sources": [e.to_dict() for e in sorted(
                self.sources_meta.values(), key=lambda e: (e.priority, e.display_name),
            )],
        }


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_YAML_PATH = _PROJECT_ROOT / "sources.yaml"


def _parse_board_section(
    raw: Any,
    ats_type: str,
    set_name: str,
    key: str,
) -> tuple[dict[str, str], dict[str, SourceEntry]]:
    """Parse a boards section supporting both simple and enriched formats.

    Returns:
        (simple_dict, meta_dict) where simple_dict is slug → display_name
        and meta_dict is "ats_type:slug" → SourceEntry.
    """
    if not raw or not isinstance(raw, dict):
        if raw is not None:
            logger.warning(
                "sources.yaml '%s'.%s: expected dict, got %s",
                set_name, key, type(raw).__name__,
            )
        return {}, {}

    simple: dict[str, str] = {}
    meta: dict[str, SourceEntry] = {}

    for slug_raw, value in raw.items():
        slug = str(slug_raw).strip()
        if not slug:
            continue

        if isinstance(value, str):
            # Simple format: slug: "Company Name"
            display = value.strip() or slug
            simple[slug] = display
            meta[f"{ats_type}:{slug}"] = SourceEntry(
                display_name=display, ats_type=ats_type, slug=slug,
            )
        elif isinstance(value, dict):
            # Enriched format
            display = str(value.get("display_name", slug)).strip()
            priority = _coerce_priority(value.get("priority", 5))
            raw_tags = value.get("focus_tags") or []
            if isinstance(raw_tags, list):
                focus_tags = tuple(str(t).strip() for t in raw_tags if t)
            else:
                focus_tags = ()
            noise = str(value.get("noise_risk", "medium")).lower()
            if noise not in _VALID_NOISE_RISK:
                noise = "medium"
            raw_regions = value.get("regions") or []
            if isinstance(raw_regions, list):
                regions = tuple(str(r).strip() for r in raw_regions if r)
            else:
                regions = ()
            notes = str(value.get("notes", "")).strip()

            simple[slug] = display
            meta[f"{ats_type}:{slug}"] = SourceEntry(
                display_name=display,
                ats_type=ats_type,
                slug=slug,
                priority=priority,
                focus_tags=focus_tags,
                noise_risk=noise,
                regions=regions,
                notes=notes,
            )
        else:
            # Fallback: use slug as display name
            simple[slug] = slug
            meta[f"{ats_type}:{slug}"] = SourceEntry(
                display_name=slug, ats_type=ats_type, slug=slug,
            )

    return simple, meta


def _validate_source_set(entry: dict[str, Any], idx: int) -> SourceSet | None:
    """Validate a single YAML entry and return a SourceSet or None."""
    name = entry.get("name")
    if not name or not isinstance(name, str):
        logger.warning("sources.yaml entry %d: missing or invalid 'name', skipping", idx)
        return None

    description = entry.get("description", "")
    if not isinstance(description, str):
        description = str(description)

    boards, boards_meta = _parse_board_section(
        entry.get("greenhouse_boards") or entry.get("boards"),
        "greenhouse", name, "greenhouse_boards",
    )
    lever, lever_meta = _parse_board_section(
        entry.get("lever_boards"), "lever", name, "lever_boards",
    )
    ashby, ashby_meta = _parse_board_section(
        entry.get("ashby_boards"), "ashby", name, "ashby_boards",
    )

    if not boards and not lever and not ashby:
        logger.warning("sources.yaml '%s': no boards defined, skipping", name)
        return None

    all_meta = {**boards_meta, **lever_meta, **ashby_meta}

    return SourceSet(
        name=name.strip(),
        description=description.strip(),
        boards=boards,
        lever_boards=lever,
        ashby_boards=ashby,
        sources_meta=all_meta,
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

    # Support both top-level list and wrapped { source_sets: [...] } format
    if isinstance(raw, dict) and "source_sets" in raw:
        raw = raw["source_sets"]

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
# Helper to build a SourceSet from simple dicts (for fallback / tests)
# ---------------------------------------------------------------------------

def _make_source_set(
    name: str,
    description: str,
    boards: dict[str, str] | None = None,
    lever_boards: dict[str, str] | None = None,
    ashby_boards: dict[str, str] | None = None,
) -> SourceSet:
    """Create a SourceSet with auto-generated sources_meta."""
    boards = boards or {}
    lever_boards = lever_boards or {}
    ashby_boards = ashby_boards or {}
    meta: dict[str, SourceEntry] = {}
    for slug, display in boards.items():
        meta[f"greenhouse:{slug}"] = SourceEntry(
            display_name=display, ats_type="greenhouse", slug=slug,
        )
    for slug, display in lever_boards.items():
        meta[f"lever:{slug}"] = SourceEntry(
            display_name=display, ats_type="lever", slug=slug,
        )
    for slug, display in ashby_boards.items():
        meta[f"ashby:{slug}"] = SourceEntry(
            display_name=display, ats_type="ashby", slug=slug,
        )
    return SourceSet(
        name=name,
        description=description,
        boards=boards,
        lever_boards=lever_boards,
        ashby_boards=ashby_boards,
        sources_meta=meta,
    )


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

    _register(_make_source_set(
        name="semiconductor_exec_core",
        description=(
            "Core semiconductor and AI-silicon companies with executive "
            "operations, supply-chain, and industrialization roles."
        ),
        boards={
            "samsungsemiconductor": "Samsung Semiconductor",
            "lattice": "Lattice Semiconductor",
            "tenstorrent": "Tenstorrent",
            "ambiqmicroinc": "Ambiq Micro",
            "cerebrassystems": "Cerebras Systems",
            "sambanovasystems": "SambaNova Systems",
            "lightmatter": "Lightmatter",
            "atomicmachines": "Atomic Machines",
        },
        lever_boards={
            "rigetti": "Rigetti Computing",
            "aeva": "Aeva Technologies",
        },
        ashby_boards={
            "blacksemiconductor": "Black Semiconductor",
        },
    ))

    _register(_make_source_set(
        name="photonics_mems_ops",
        description=(
            "Photonics, MEMS, lidar, and advanced sensing companies "
            "with operations and executive roles."
        ),
        boards={
            "anellophotonics": "Anello Photonics",
            "lightmatter": "Lightmatter",
            "atomicmachines": "Atomic Machines",
        },
        lever_boards={
            "neye-systems-inc.": "Neye Systems",
            "lumotive": "Lumotive",
        },
        ashby_boards={
            "voyant-photonics": "Voyant Photonics",
            "lumilens": "Lumilens",
        },
    ))

    _register(_make_source_set(
        name="broad_hardware_supply_chain",
        description=(
            "Advanced-hardware, defense-tech, aerospace, and industrial "
            "manufacturing companies with executive supply-chain roles."
        ),
        boards={
            "andurilindustries": "Anduril Industries",
            "markforged": "Markforged",
            "formlabs": "Formlabs",
            "lucidmotors": "Lucid Motors",
            "relativity": "Relativity Space",
            "rocketlab": "Rocket Lab",
            "astranis": "Astranis",
        },
        lever_boards={
            "aeva": "Aeva Technologies",
            "hermeus": "Hermeus",
        },
        ashby_boards={
            "taaraconnect": "Taara Connect",
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


def describe_source_set(name: str) -> dict[str, Any]:
    """Return a description dict for a source set (for API / templates).

    Raises:
        KeyError: If no source set with *name* exists.
    """
    return get_source_set(name).describe()


def describe_all_source_sets() -> list[dict[str, Any]]:
    """Return description dicts for all registered source sets."""
    return [ss.describe() for ss in list_source_sets()]
