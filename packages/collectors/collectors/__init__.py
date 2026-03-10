"""Collector base interface and implementations for Exec Radar."""

from collectors.base import BaseCollector
from collectors.http_collector import HttpCollector

__all__ = ["BaseCollector", "HttpCollector"]
