"""Simple rule-based normalizer implementation."""

from __future__ import annotations

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
            title=raw.title.strip(),
            company=raw.company,
            location=raw.location,
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

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags (naive approach)."""
        return re.sub(r"<[^>]+>", "", text).strip()

    @staticmethod
    def _extract_tags(title: str, description: str) -> list[str]:
        """Extract keyword tags from title and description."""
        keywords = [
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
        ]
        combined = f"{title} {description}".lower()
        return sorted({kw for kw in keywords if kw.lower() in combined})
