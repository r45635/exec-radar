"""Simple rule-based normalizer implementation."""

from __future__ import annotations

import html
import re

from packages.normalizers.base import BaseNormalizer
from packages.schemas.normalized_job import (
    NormalizedJobPosting,
    RemotePolicy,
    SeniorityLevel,
)
from packages.schemas.raw_job import RawJobPosting

_SENIORITY_PATTERNS: list[tuple[re.Pattern[str], SeniorityLevel]] = [
    (re.compile(r"\bC(?:hief|EO|OO|FO|TO|IO)\b", re.IGNORECASE), SeniorityLevel.C_LEVEL),
    (re.compile(r"\bSVP\b|\bSenior Vice President\b", re.IGNORECASE), SeniorityLevel.SVP),
    (re.compile(r"\bVP\b|\bVice President\b", re.IGNORECASE), SeniorityLevel.VP),
    (re.compile(r"\bDirector\b", re.IGNORECASE), SeniorityLevel.DIRECTOR),
    (re.compile(r"\bHead of\b", re.IGNORECASE), SeniorityLevel.HEAD),
]

_REMOTE_PATTERNS: list[tuple[re.Pattern[str], RemotePolicy]] = [
    (re.compile(r"\bremote\b", re.IGNORECASE), RemotePolicy.REMOTE),
    (re.compile(r"\bhybrid\b", re.IGNORECASE), RemotePolicy.HYBRID),
    (re.compile(r"\bonsite\b|\bon-site\b|\bin.office\b", re.IGNORECASE), RemotePolicy.ONSITE),
]

_SALARY_RE = re.compile(
    r"[\$\u00a3\u20ac]?\s*([\d,]+(?:\.\d+)?)\s*(?:[\u2013\u2014-]\s*[\$\u00a3\u20ac]?\s*([\d,]+(?:\.\d+)?))?",
)
_CURRENCY_RE = re.compile(r"([\$\u00a3\u20ac])")
_CURRENCY_MAP: dict[str, str] = {"$": "USD", "£": "GBP", "€": "EUR"}


class SimpleNormalizer(BaseNormalizer):
    """Rule-based normalizer using regex heuristics.

    Suitable for development and as a baseline.  Production systems
    should layer NLP or LLM-based extraction on top.
    """

    def normalize(self, raw: RawJobPosting) -> NormalizedJobPosting:
        """Normalize a raw posting into canonical form.

        Args:
            raw: The raw posting to transform.

        Returns:
            A :class:`NormalizedJobPosting` with inferred fields.
        """
        seniority = self._infer_seniority(raw.title)
        remote_policy = self._infer_remote_policy(raw.location or "", raw.description)
        salary_min, salary_max, currency = self._parse_salary(raw.salary_raw)
        tags = self._extract_tags(raw.title, raw.description)

        return NormalizedJobPosting(
            source=raw.source,
            source_id=raw.source_id,
            source_url=raw.source_url,
            title=self._normalize_unicode(raw.title.strip()),
            company=self._normalize_unicode(raw.company) if raw.company else None,
            location=self._normalize_unicode(raw.location) if raw.location else None,
            remote_policy=remote_policy,
            seniority=seniority,
            description_plain=self._strip_html(raw.description),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            tags=tags,
            posted_at=raw.posted_at,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """Normalize special Unicode characters to ASCII equivalents."""
        if not text:
            return text
        text = text.replace("\u2014", "-")  # em dash → hyphen
        text = text.replace("\u2013", "-")  # en dash → hyphen
        text = text.replace("\u2026", "...")  # ellipsis → three dots
        text = text.replace("\u201c", '"')  # left double quote
        text = text.replace("\u201d", '"')  # right double quote
        text = text.replace("\u2018", "'")  # left single quote
        text = text.replace("\u2019", "'")  # right single quote
        return text

    @staticmethod
    def _infer_seniority(title: str) -> SeniorityLevel:
        """Match the first seniority pattern found in the title."""
        for pattern, level in _SENIORITY_PATTERNS:
            if pattern.search(title):
                return level
        return SeniorityLevel.OTHER

    @staticmethod
    def _infer_remote_policy(location: str, description: str) -> RemotePolicy:
        """Determine remote policy from location and description text."""
        combined = f"{location} {description}"
        for pattern, policy in _REMOTE_PATTERNS:
            if pattern.search(combined):
                return policy
        return RemotePolicy.UNKNOWN

    @staticmethod
    def _parse_salary(
        salary_raw: str | None,
    ) -> tuple[float | None, float | None, str | None]:
        """Extract numeric salary bounds and currency."""
        if not salary_raw:
            return None, None, None
        currency_match = _CURRENCY_RE.search(salary_raw)
        currency = _CURRENCY_MAP.get(currency_match.group(1), None) if currency_match else None
        match = _SALARY_RE.search(salary_raw)
        if not match:
            return None, None, currency
        low = float(match.group(1).replace(",", ""))
        high = float(match.group(2).replace(",", "")) if match.group(2) else None
        return low, high, currency

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags, decode HTML entities, and normalize Unicode."""
        # Decode HTML entities (may be double-encoded, so decode twice)
        decoded = html.unescape(html.unescape(text))
        # Remove HTML tags
        stripped = re.sub(r"<[^>]+>", "", decoded)
        # Clean up any remaining entities
        cleaned = re.sub(r"&\w+;", "", stripped)  # Remove &nbsp;, &amp;, etc.
        # Normalize Unicode characters
        cleaned = self._normalize_unicode(cleaned)
        # Clean up excessive whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _extract_tags(title: str, description: str) -> list[str]:
        """Extract keyword tags from title and description."""
        keywords = [
            # Core operations
            "operations",
            "supply chain",
            "logistics",
            "strategy",
            "transformation",
            "change management",
            "P&L",
            "manufacturing",
            "digital",
            "healthcare",
            "finance",
            # Semiconductor & electronics
            "semiconductor",
            "wafer",
            "fab",
            "foundry",
            "cleanroom",
            "yield",
            "silicon",
            "chip",
            "asic",
            "mems",
            "electronics",
            # Automotive & quality
            "automotive",
            "iatf",
            "apqp",
            "ppap",
            "fmea",
            "oem",
            "powertrain",
            # Executive / operational excellence
            "operational excellence",
            "continuous improvement",
            "lean",
            "six sigma",
            "kaizen",
            "kpi",
            "restructuring",
            "turnaround",
            # Supply chain & industrialization
            "procurement",
            "sourcing",
            "inventory",
            "warehouse",
            "distribution",
            "npi",
            "industrialization",
            "ramp-up",
            "scale-up",
            "capex",
            # Scope indicators
            "global",
            "multi-site",
            "international",
            "business unit",
            "regional",
            "site",
            "single site",
            "plant",
            "cross-functional",
            "enterprise-wide",
            "worldwide",
            # Industries
            "aerospace",
            "defense",
            "energy",
            "chemicals",
            "medical devices",
        ]
        combined = f"{title} {description}".lower()
        return sorted({kw for kw in keywords if kw.lower() in combined})
