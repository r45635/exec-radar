"""Collector package — source-specific data ingestion."""

from packages.collectors.base import BaseCollector
from packages.collectors.composite_collector import CompositeCollector
from packages.collectors.greenhouse_collector import GreenhouseCollector
from packages.collectors.mock_collector import MockCollector

__all__ = [
    "BaseCollector",
    "CompositeCollector",
    "GreenhouseCollector",
    "MockCollector",
]
