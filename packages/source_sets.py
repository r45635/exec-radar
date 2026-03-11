"""Named source sets — curated board lists for different use cases.

Each source set defines boards/slugs across multiple ATS platforms:
Greenhouse, Lever, and Ashby.  Source sets can be referenced by name
from a :class:`TargetProfile` or via the
``EXEC_RADAR_SOURCE_SET`` environment variable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
# Registry of built-in source sets
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, SourceSet] = {}


def _register(ss: SourceSet) -> SourceSet:
    _REGISTRY[ss.name] = ss
    return ss


# ── Semiconductor executive operations ────────────────────────────────────
_register(SourceSet(
    name="semiconductor_exec",
    description=(
        "Semiconductor companies with executive operations, supply-chain, "
        "and industrialization roles (IDM, fabless, foundry, OSAT)."
    ),
    boards={
        "lattice": "Lattice Semiconductor",
        "tenstorrent": "Tenstorrent",
        "cerebrassystems": "Cerebras Systems",
        "skyworksinc": "Skyworks Solutions",
        "maborc": "Marvell Technology",
        "monaborc": "Monolithic Power Systems",
        "onsaboremi": "onsemi",
        "maxlinear": "MaxLinear",
        "allegromicrosystems": "Allegro Microsystems",
        "sifive": "SiFive",
        "achronix": "Achronix Semiconductor",
        "rambusinc": "Rambus",
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

# ── Deep-tech / hardware (broader than semi) ─────────────────────────────
_register(SourceSet(
    name="deeptech_hardware",
    description=(
        "AI-hardware, photonics, quantum, and advanced computing "
        "companies with executive and operations roles."
    ),
    boards={
        "graphcore": "Graphcore",
        "lightmatter": "Lightmatter",
        "sambanovasystems": "SambaNova Systems",
        "cerebrassystems": "Cerebras Systems",
        "tenstorrent": "Tenstorrent",
        "dabormatrix": "d-Matrix",
        "groq": "Groq",
        "mythic": "Mythic AI",
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

# ── Broad executive operations (cross-industry) ──────────────────────────
_register(SourceSet(
    name="broad_exec_ops",
    description=(
        "Large companies across semiconductor, automotive, aerospace, "
        "and industrial manufacturing with executive-level postings."
    ),
    boards={
        "lattice": "Lattice Semiconductor",
        "tenstorrent": "Tenstorrent",
        "cerebrassystems": "Cerebras Systems",
        "skyworksinc": "Skyworks Solutions",
        "rivian": "Rivian",
        "relativityspace": "Relativity Space",
        "andurilindustries": "Anduril Industries",
        "zipline": "Zipline",
        "jobyaviation": "Joby Aviation",
        "commonspirit": "CommonSpirit Health",
    },
    lever_boards={
        "aeva": "Aeva Technologies",
        "plaid": "Plaid",
    },
    ashby_boards={
        "ramp": "Ramp",
        "cohere": "Cohere",
    },
))


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
