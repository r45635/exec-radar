"""Ranker package — job-fit scoring logic."""

from packages.rankers.base import BaseRanker
from packages.rankers.rule_based_ranker import RuleBasedRanker

__all__ = [
    "BaseRanker",
    "RuleBasedRanker",
]
