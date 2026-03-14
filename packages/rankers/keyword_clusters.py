"""Keyword clusters — domain-specific keyword groups for scoring.

Each cluster represents a functional or industry domain.  The ranker
computes per-cluster overlap scores and aggregates them into the
``keyword_clusters`` dimension.

Usage::

    from packages.rankers.keyword_clusters import (
        CLUSTERS,
        score_clusters,
    )

    scores = score_clusters(tags, description)
    # => {"semiconductor_manufacturing": 0.6, ...}
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordCluster:
    """A named group of related keywords with a relevance weight."""

    name: str
    weight: float  # relative importance within the cluster dimension
    keywords: frozenset[str]


# ── Cluster definitions ──────────────────────────────────────────
CLUSTERS: tuple[KeywordCluster, ...] = (
    KeywordCluster(
        name="semiconductor_manufacturing",
        weight=0.20,
        keywords=frozenset(
            {
                "semiconductor",
                "wafer",
                "fab",
                "foundry",
                "cleanroom",
                "photolithography",
                "etching",
                "deposition",
                "packaging",
                "test engineering",
                "yield",
                "process engineering",
                "silicon",
                "chip",
                "integrated circuit",
                "ic",
                "asic",
                "mems",
                "back-end",
                "front-end",
            }
        ),
    ),
    KeywordCluster(
        name="fabless_foundry_osat",
        weight=0.20,
        keywords=frozenset(
            {
                "fabless",
                "foundry",
                "osat",
                "outsourced manufacturing",
                "subcontractor",
                "backend",
                "assembly",
                "test",
                "wafer sort",
                "final test",
                "packaging",
                "advanced packaging",
                "supplier quality",
                "external manufacturing",
                "contract manufacturing",
                "semiconductor manufacturing",
            }
        ),
    ),
    KeywordCluster(
        name="automotive_quality",
        weight=0.15,
        keywords=frozenset(
            {
                "automotive",
                "iatf 16949",
                "iatf",
                "apqp",
                "ppap",
                "fmea",
                "spc",
                "msa",
                "8d",
                "iso/ts",
                "oem",
                "tier 1",
                "tier 2",
                "vehicle",
                "homologation",
                "adas",
                "powertrain",
                "ev",
                "electric vehicle",
            }
        ),
    ),
    KeywordCluster(
        name="executive_operations_leadership",
        weight=0.15,
        keywords=frozenset(
            {
                "operations",
                "operational excellence",
                "p&l",
                "profit and loss",
                "transformation",
                "restructuring",
                "turnaround",
                "change management",
                "continuous improvement",
                "lean",
                "six sigma",
                "kaizen",
                "tps",
                "total productive maintenance",
                "tpm",
                "value stream",
                "business process",
                "kpi",
                "okr",
                "balanced scorecard",
                "strategic planning",
                "executive leadership",
            }
        ),
    ),
    KeywordCluster(
        name="supply_chain_industrialization",
        weight=0.15,
        keywords=frozenset(
            {
                "supply chain",
                "procurement",
                "sourcing",
                "logistics",
                "inventory",
                "warehouse",
                "distribution",
                "s&op",
                "demand planning",
                "npi",
                "new product introduction",
                "industrialization",
                "ramp-up",
                "scale-up",
                "transfer",
                "localization",
                "make or buy",
                "capex",
                "capacity planning",
            }
        ),
    ),
    KeywordCluster(
        name="semiconductor_process",
        weight=0.15,
        keywords=frozenset(
            {
                "process engineering",
                "process integration",
                "process development",
                "thin film",
                "etch",
                "cvd",
                "pvd",
                "cmp",
                "lithography",
                "photolithography",
                "diffusion",
                "implant",
                "ion implantation",
                "metrology",
                "defect",
                "defectivity",
                "contamination",
                "process control",
                "spc",
                "recipe",
                "chamber",
                "tool qualification",
                "wafer fabrication",
                "technology node",
                "design rule",
                "dram",
                "nand",
                "finfet",
                "gaafet",
                "gate-all-around",
                "euvl",
                "euv",
            }
        ),
    ),
)


def score_clusters(
    tags: list[str],
    description: str,
) -> dict[str, float]:
    """Compute per-cluster overlap scores.

    For each cluster the score is the fraction of cluster keywords
    found in the combined tag-set + description text.  A minimum of
    one keyword must match to produce a non-zero score.

    Args:
        tags: Extracted tags from the posting.
        description: Plain-text description body.

    Returns:
        Dict mapping cluster name → score in [0, 1].
    """
    combined = " ".join(tags).lower() + " " + description.lower()
    result: dict[str, float] = {}
    for cluster in CLUSTERS:
        hits = 0
        for kw in cluster.keywords:
            # Use word-boundary matching for short keywords to avoid
            # false positives (e.g. "ic" matching inside "applications").
            if len(kw) <= 3:
                if re.search(rf"\b{re.escape(kw)}\b", combined):
                    hits += 1
            elif kw in combined:
                hits += 1
        result[cluster.name] = hits / len(cluster.keywords) if cluster.keywords else 0.0
    return result


def aggregate_cluster_score(cluster_scores: dict[str, float]) -> float:
    """Weight-average the per-cluster scores into a single dimension value.

    Only clusters with at least one keyword hit contribute to the
    denominator, so unrelated clusters (e.g. semiconductor clusters
    for a non-semiconductor job) don't dilute the score.

    Returns:
        A float in [0, 1].
    """
    active_weight = sum(
        c.weight for c in CLUSTERS if cluster_scores.get(c.name, 0.0) > 0
    )
    if active_weight == 0.0:
        return 0.0
    weighted = sum(
        cluster_scores.get(c.name, 0.0) * c.weight for c in CLUSTERS
    )
    return min(1.0, weighted / active_weight)
