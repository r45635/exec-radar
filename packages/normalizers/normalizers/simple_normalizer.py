"""Simple rule-based normalizer using regex and keyword matching."""

import re
import uuid

from schemas import NormalizedJobPosting, RawJobPosting
from schemas.normalized_job_posting import EmploymentType, SeniorityLevel

from .base import BaseNormalizer

# ---------------------------------------------------------------------------
# Keyword maps used to infer seniority and employment type from the title.
# These are intentionally minimal – extend them as the platform grows.
# ---------------------------------------------------------------------------

_SENIORITY_MAP: list[tuple[list[str], SeniorityLevel]] = [
    # VP must be checked before C_SUITE to avoid "president" matching "vice president"
    (["vice president", "vp"], SeniorityLevel.VP),
    (["chief", "cto", "coo", "cfo", "ceo", "president"], SeniorityLevel.C_SUITE),
    (["director"], SeniorityLevel.DIRECTOR),
    (["senior", "sr.", "sr", "lead", "principal", "staff"], SeniorityLevel.SENIOR),
    (["associate", "junior", "jr.", "jr"], SeniorityLevel.ENTRY),
]

_EMPLOYMENT_MAP: list[tuple[list[str], EmploymentType]] = [
    (["interim", "fractional"], EmploymentType.INTERIM),
    (["board", "advisory", "advisor"], EmploymentType.BOARD),
    (["contract", "contractor", "freelance"], EmploymentType.CONTRACT),
    (["part-time", "part time"], EmploymentType.PART_TIME),
]

_REMOTE_KEYWORDS = ["remote", "distributed", "work from home", "wfh", "anywhere"]

# Match patterns like "$150,000 - $200,000" or "150k-200k"
_SALARY_RE = re.compile(
    r"\$?([\d,]+(?:\.\d+)?)\s*[kK]?\s*[-–to]+\s*\$?([\d,]+(?:\.\d+)?)\s*[kK]?",
)

# Common tech / executive skills to extract
_SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++",
    "aws", "gcp", "azure", "kubernetes", "docker", "terraform",
    "postgresql", "mysql", "redis", "mongodb",
    "fastapi", "django", "flask", "react", "node.js",
    "machine learning", "llm", "ai", "data science",
    "leadership", "strategy", "p&l", "budget", "stakeholder",
    "agile", "scrum", "devops", "ci/cd",
]


def _infer_seniority(title: str) -> SeniorityLevel:
    lower = title.lower()
    # Use word-boundary matching to avoid partial hits (e.g. "cto" inside "director")
    words_and_phrases = re.split(r"[\s,/|]+", lower)
    for keywords, level in _SENIORITY_MAP:
        for kw in keywords:
            # Multi-word keywords: check as substring; single words: exact token match
            if " " in kw:
                if kw in lower:
                    return level
            elif kw in words_and_phrases:
                return level
    return SeniorityLevel.UNKNOWN


def _infer_employment_type(title: str, description: str | None) -> EmploymentType:
    text = (title + " " + (description or "")).lower()
    for keywords, emp_type in _EMPLOYMENT_MAP:
        if any(kw in text for kw in keywords):
            return emp_type
    return EmploymentType.FULL_TIME


def _infer_remote(location: str | None, description: str | None) -> bool:
    text = ((location or "") + " " + (description or "")).lower()
    return any(kw in text for kw in _REMOTE_KEYWORDS)


def _parse_salary(salary_raw: str | None) -> tuple[float | None, float | None]:
    if not salary_raw:
        return None, None
    match = _SALARY_RE.search(salary_raw)
    if not match:
        return None, None
    try:
        lo_str = match.group(1).replace(",", "")
        hi_str = match.group(2).replace(",", "")
        lo = float(lo_str)
        hi = float(hi_str)
        # Convert shorthand like 150k → 150_000
        if "k" in salary_raw.lower():
            if lo < 10_000:
                lo *= 1_000
            if hi < 10_000:
                hi *= 1_000
        return lo, hi
    except ValueError:
        return None, None


def _extract_skills(description: str | None) -> list[str]:
    if not description:
        return []
    lower = description.lower()
    return [skill for skill in _SKILL_KEYWORDS if skill in lower]


def _extract_keywords(title: str, description: str | None) -> list[str]:
    text = (title + " " + (description or "")).lower()
    words = re.findall(r"\b[a-z][a-z\+\.#]{2,}\b", text)
    # Deduplicate while preserving first-occurrence order
    seen: set[str] = set()
    unique: list[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique.append(word)
    return unique[:30]


class SimpleNormalizer(BaseNormalizer):
    """Rule-based normalizer using regex and keyword matching.

    This implementation is intentionally straightforward.  It infers seniority,
    employment type, remote status, salary range, skills, and keywords without
    any external dependencies.  Replace or augment with ML-based normalization
    as the platform matures.
    """

    def normalize(self, raw: RawJobPosting) -> NormalizedJobPosting:
        """Apply heuristic normalization to *raw*.

        Args:
            raw: Source-faithful job posting.

        Returns:
            Normalized posting ready for scoring.
        """
        salary_min, salary_max = _parse_salary(raw.salary_raw)

        return NormalizedJobPosting(
            id=str(uuid.uuid4()),
            source=raw.source,
            source_id=raw.source_id,
            url=raw.url,
            title=raw.title.strip(),
            seniority=_infer_seniority(raw.title),
            employment_type=_infer_employment_type(raw.title, raw.description),
            company=raw.company.strip(),
            location=raw.location,
            remote=_infer_remote(raw.location, raw.description),
            salary_min=salary_min,
            salary_max=salary_max,
            description=raw.description,
            skills=_extract_skills(raw.description),
            keywords=_extract_keywords(raw.title, raw.description),
            posted_at=raw.posted_at,
        )
