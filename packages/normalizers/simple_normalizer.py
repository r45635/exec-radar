"""Simple rule-based normalizer implementation."""

from __future__ import annotations

import html
import re

from packages.normalizers.base import BaseNormalizer
from packages.normalizers.title_families import resolve_title_family
from packages.schemas.normalized_job import (
    IndustryFamily,
    JobFunctionFamily,
    NormalizedJobPosting,
    RemotePolicy,
    ScopeLevel,
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
        description_plain = self._strip_html(raw.description)
        title_clean = self._normalize_unicode(raw.title.strip())

        # Extended normalization fields
        title_family = resolve_title_family(title_clean)
        combined = f"{title_clean} {description_plain}".lower()
        industry_family = self._infer_industry_family(tags, combined)
        job_function_family = self._infer_job_function_family(title_clean, title_family)
        scope_level = self._infer_scope_level(tags, combined)
        is_software_heavy = self._detect_software_heavy(combined)
        is_gtm_heavy = self._detect_gtm_heavy(combined)
        is_semiconductor_like = self._detect_semiconductor_like(tags, combined)

        return NormalizedJobPosting(
            source=raw.source,
            source_id=raw.source_id,
            source_url=raw.source_url,
            title=title_clean,
            company=self._normalize_unicode(raw.company) if raw.company else None,
            location=self._normalize_unicode(raw.location) if raw.location else None,
            remote_policy=remote_policy,
            seniority=seniority,
            description_plain=description_plain,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            tags=tags,
            title_family=title_family,
            industry_family=industry_family,
            job_function_family=job_function_family,
            scope_level=scope_level,
            is_software_heavy=is_software_heavy,
            is_gtm_heavy=is_gtm_heavy,
            is_semiconductor_like=is_semiconductor_like,
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

    # ------------------------------------------------------------------
    # Extended field inference
    # ------------------------------------------------------------------

    _SEMI_KEYWORDS = frozenset({
        "semiconductor", "wafer", "fab", "foundry", "cleanroom", "silicon",
        "chip", "asic", "mems", "osat", "finfet", "gaafet", "euv", "dram",
        "nand", "die", "substrate", "epitaxy", "lithography", "etch",
        "diffusion", "implant", "backend operations", "yield",
    })

    _AUTO_KEYWORDS = frozenset({
        "automotive", "iatf", "apqp", "ppap", "fmea", "oem", "powertrain",
        "vehicle", "ev ", "electric vehicle", "adas", "tier 1",
    })

    _AERO_KEYWORDS = frozenset({
        "aerospace", "defense", "defence", "military", "satellite",
        "avionics", "propulsion", "missile", "aircraft",
    })

    _INDUSTRIAL_MFG_KEYWORDS = frozenset({
        "manufacturing", "industrial", "production", "factory", "plant",
        "assembly", "machining", "injection molding", "casting", "stamping",
        "metal", "plastics", "packaging",
    })

    _ENERGY_KEYWORDS = frozenset({
        "energy", "chemicals", "chemical", "oil", "gas", "petroleum",
        "refinery", "renewables", "solar", "wind", "battery", "hydrogen",
    })

    _MEDDEV_KEYWORDS = frozenset({
        "medical devices", "medtech", "biomedical", "implant", "surgical",
        "diagnostic", "fda", "iso 13485", "class ii", "class iii",
    })

    _SOFTWARE_SIGNALS = frozenset({
        "software", "saas", "devops", "kubernetes", "docker",
        "microservices", "frontend", "backend developer", "full stack",
        "react", "angular", "node.js", "python developer", "java developer",
        "cloud native", "ci/cd", "agile software",
    })

    _GTM_SIGNALS = frozenset({
        "demand generation", "revenue operations", "sdr", "bdr",
        "account executive", "customer success", "growth marketing",
        "sales enablement", "marketing automation", "pipeline generation",
        "go-to-market", "gtm",
    })

    _GLOBAL_SCOPE_MARKERS = frozenset({
        "global", "worldwide", "multi-site", "international",
        "cross-functional", "enterprise-wide", "multi-country",
        "multi-region", "multiple sites", "multiple plants",
    })

    _NARROW_SCOPE_MARKERS = frozenset({
        "single site", "one plant", "local plant", "site-level",
        "plant-level", "single facility",
    })

    # Title family → function family mapping
    _FAMILY_TO_FUNCTION: dict[str, JobFunctionFamily] = {
        "COO": JobFunctionFamily.OPERATIONS,
        "VP_OPERATIONS": JobFunctionFamily.OPERATIONS,
        "HEAD_OPERATIONS": JobFunctionFamily.OPERATIONS,
        "GM_OPERATIONS": JobFunctionFamily.GENERAL_MANAGEMENT,
        "VP_MANUFACTURING": JobFunctionFamily.MANUFACTURING,
        "HEAD_MANUFACTURING": JobFunctionFamily.MANUFACTURING,
        "VP_SUPPLY_CHAIN": JobFunctionFamily.SUPPLY_CHAIN,
        "HEAD_SUPPLY_CHAIN": JobFunctionFamily.SUPPLY_CHAIN,
        "VP_QUALITY": JobFunctionFamily.QUALITY,
        "HEAD_QUALITY": JobFunctionFamily.QUALITY,
        "VP_ENGINEERING": JobFunctionFamily.ENGINEERING,
        "HEAD_TRANSFORMATION": JobFunctionFamily.TRANSFORMATION,
        "PLANT_DIRECTOR": JobFunctionFamily.OPERATIONS,
        "CEO": JobFunctionFamily.GENERAL_MANAGEMENT,
        "CFO": JobFunctionFamily.FINANCE,
        "CTO": JobFunctionFamily.TECHNOLOGY,
        "CHRO": JobFunctionFamily.PEOPLE,
        "CMO": JobFunctionFamily.COMMERCIAL,
        "CSO": JobFunctionFamily.STRATEGY,
    }

    @classmethod
    def _infer_industry_family(cls, tags: list[str], combined: str) -> IndustryFamily:
        """Classify industry from tags and combined text."""
        def _count(keywords: frozenset[str]) -> int:
            return sum(1 for kw in keywords if kw in combined)

        semi = _count(cls._SEMI_KEYWORDS)
        auto = _count(cls._AUTO_KEYWORDS)
        aero = _count(cls._AERO_KEYWORDS)
        indm = _count(cls._INDUSTRIAL_MFG_KEYWORDS)
        ener = _count(cls._ENERGY_KEYWORDS)
        medd = _count(cls._MEDDEV_KEYWORDS)
        soft = _count(cls._SOFTWARE_SIGNALS)

        scores = [
            (semi, IndustryFamily.SEMICONDUCTOR),
            (auto, IndustryFamily.AUTOMOTIVE),
            (aero, IndustryFamily.AEROSPACE_DEFENSE),
            (indm, IndustryFamily.INDUSTRIAL_MANUFACTURING),
            (ener, IndustryFamily.ENERGY_CHEMICALS),
            (medd, IndustryFamily.MEDICAL_DEVICES),
            (soft, IndustryFamily.SOFTWARE_CLOUD),
        ]
        best_count, best_family = max(scores, key=lambda x: x[0])
        if best_count >= 2:
            return best_family
        return IndustryFamily.OTHER

    @classmethod
    def _infer_job_function_family(
        cls, title: str, title_family: str | None,
    ) -> JobFunctionFamily:
        """Classify job function from title family or title text."""
        if title_family and title_family in cls._FAMILY_TO_FUNCTION:
            return cls._FAMILY_TO_FUNCTION[title_family]

        lower = title.lower()
        if any(kw in lower for kw in ("operations", "ops ")):
            return JobFunctionFamily.OPERATIONS
        if "supply chain" in lower or "procurement" in lower or "logistics" in lower:
            return JobFunctionFamily.SUPPLY_CHAIN
        if "manufactur" in lower or "production" in lower:
            return JobFunctionFamily.MANUFACTURING
        if "quality" in lower:
            return JobFunctionFamily.QUALITY
        if "engineer" in lower:
            return JobFunctionFamily.ENGINEERING
        if "transform" in lower:
            return JobFunctionFamily.TRANSFORMATION
        return JobFunctionFamily.OTHER

    @classmethod
    def _infer_scope_level(cls, tags: list[str], combined: str) -> ScopeLevel:
        """Classify operational scope."""
        global_hits = sum(1 for m in cls._GLOBAL_SCOPE_MARKERS if m in combined)
        narrow_hits = sum(1 for m in cls._NARROW_SCOPE_MARKERS if m in combined)

        if global_hits >= 2:
            return ScopeLevel.GLOBAL
        if global_hits == 1 and narrow_hits == 0:
            return ScopeLevel.GLOBAL
        if narrow_hits >= 1 and global_hits == 0:
            return ScopeLevel.SITE
        if "regional" in combined or "business unit" in combined:
            return ScopeLevel.REGIONAL
        return ScopeLevel.UNKNOWN

    @classmethod
    def _detect_software_heavy(cls, combined: str) -> bool:
        """Detect if the role is software-dominated."""
        return sum(1 for kw in cls._SOFTWARE_SIGNALS if kw in combined) >= 3

    @classmethod
    def _detect_gtm_heavy(cls, combined: str) -> bool:
        """Detect if the role is GTM/sales-dominated."""
        return sum(1 for kw in cls._GTM_SIGNALS if kw in combined) >= 2

    @classmethod
    def _detect_semiconductor_like(cls, tags: list[str], combined: str) -> bool:
        """Detect if the posting has semiconductor/industrial signals."""
        semi = sum(1 for kw in cls._SEMI_KEYWORDS if kw in combined)
        if semi >= 2:
            return True
        industrial = sum(
            1 for kw in cls._INDUSTRIAL_MFG_KEYWORDS if kw in combined
        )
        return semi >= 1 and industrial >= 1
