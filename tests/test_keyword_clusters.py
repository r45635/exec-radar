"""Tests for keyword-cluster scoring."""

from __future__ import annotations

from packages.rankers.keyword_clusters import (
    CLUSTERS,
    aggregate_cluster_score,
    score_clusters,
)


class TestScoreClusters:
    """Verify per-cluster scoring logic."""

    def test_semiconductor_hit(self) -> None:
        scores = score_clusters(
            tags=["semiconductor", "wafer", "fab"],
            description="Foundry cleanroom yield management",
        )
        assert scores["semiconductor_manufacturing"] > 0.2

    def test_fabless_foundry_osat_hit(self) -> None:
        scores = score_clusters(
            tags=["foundry", "osat", "assembly"],
            description=(
                "Manage fabless semiconductor supply chain with "
                "contract manufacturing and advanced packaging"
            ),
        )
        assert scores["fabless_foundry_osat"] > 0.2

    def test_automotive_hit(self) -> None:
        scores = score_clusters(
            tags=["automotive", "oem"],
            description="IATF 16949 audit lead, FMEA, APQP specialist",
        )
        assert scores["automotive_quality"] > 0.2

    def test_executive_ops_hit(self) -> None:
        scores = score_clusters(
            tags=["operations", "lean", "six sigma"],
            description="P&L responsibility, transformation, restructuring",
        )
        assert scores["executive_operations_leadership"] > 0.2

    def test_supply_chain_hit(self) -> None:
        scores = score_clusters(
            tags=["supply chain", "procurement"],
            description="NPI, industrialization, ramp-up, S&OP",
        )
        assert scores["supply_chain_industrialization"] > 0.2

    def test_empty_input(self) -> None:
        scores = score_clusters(tags=[], description="")
        assert all(v == 0.0 for v in scores.values())

    def test_unrelated_input(self) -> None:
        scores = score_clusters(
            tags=["python", "javascript"],
            description="Build web applications with React and Django",
        )
        assert all(v < 0.05 for v in scores.values())


class TestAggregateClusterScore:
    """Verify weighted aggregation."""

    def test_all_zeros(self) -> None:
        zeros = {c.name: 0.0 for c in CLUSTERS}
        assert aggregate_cluster_score(zeros) == 0.0

    def test_all_ones(self) -> None:
        ones = {c.name: 1.0 for c in CLUSTERS}
        assert aggregate_cluster_score(ones) == 1.0

    def test_partial(self) -> None:
        partial = {c.name: 0.5 for c in CLUSTERS}
        result = aggregate_cluster_score(partial)
        assert 0.4 <= result <= 0.6
