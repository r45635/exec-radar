"""Normalized job posting schema — canonical representation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeniorityLevel(StrEnum):
    """Seniority classification for executive roles."""

    C_LEVEL = "c_level"
    VP = "vp"
    SVP = "svp"
    DIRECTOR = "director"
    HEAD = "head"
    OTHER = "other"


class RemotePolicy(StrEnum):
    """Remote-work policy."""

    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class ScopeLevel(StrEnum):
    """Operational scope classification."""

    GLOBAL = "global"
    REGIONAL = "regional"
    SITE = "site"
    UNKNOWN = "unknown"


class JobFunctionFamily(StrEnum):
    """Broad job function classification."""

    OPERATIONS = "operations"
    SUPPLY_CHAIN = "supply_chain"
    MANUFACTURING = "manufacturing"
    QUALITY = "quality"
    ENGINEERING = "engineering"
    TRANSFORMATION = "transformation"
    GENERAL_MANAGEMENT = "general_management"
    FINANCE = "finance"
    TECHNOLOGY = "technology"
    PEOPLE = "people"
    COMMERCIAL = "commercial"
    STRATEGY = "strategy"
    OTHER = "other"


class IndustryFamily(StrEnum):
    """Industry classification for the posting."""

    SEMICONDUCTOR = "semiconductor"
    AUTOMOTIVE = "automotive"
    AEROSPACE_DEFENSE = "aerospace_defense"
    INDUSTRIAL_MANUFACTURING = "industrial_manufacturing"
    ENERGY_CHEMICALS = "energy_chemicals"
    MEDICAL_DEVICES = "medical_devices"
    CONSUMER_ELECTRONICS = "consumer_electronics"
    SOFTWARE_CLOUD = "software_cloud"
    OTHER = "other"


class NormalizedJobPosting(BaseModel):
    """A job posting transformed into Exec Radar's canonical schema.

    Created by a normalizer from a ``RawJobPosting``.  This model is
    the primary entity stored, ranked, and served by the platform.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default="", description="Deterministic ID derived from source + source_id")
    source: str = Field(..., description="Origin platform or feed")
    source_id: str = Field(..., description="Unique identifier within the source")

    @model_validator(mode="before")
    @classmethod
    def _set_deterministic_id(cls, data: Any) -> Any:
        """Derive a stable ID from ``source`` and ``source_id``.

        Using a SHA-256 hash (truncated to 32 hex chars) ensures the same
        posting always receives the same internal ID across pipeline runs.
        """
        if isinstance(data, dict) and not data.get("id"):
            source = data.get("source", "")
            source_id = data.get("source_id", "")
            data["id"] = hashlib.sha256(f"{source}:{source_id}".encode()).hexdigest()[:32]
        return data

    source_url: str | None = Field(default=None, description="Direct URL to the posting")

    title: str = Field(..., description="Cleaned job title")
    company: str | None = Field(default=None, description="Company name")
    location: str | None = Field(default=None, description="Normalized location")
    remote_policy: RemotePolicy = Field(default=RemotePolicy.UNKNOWN, description="Remote policy")

    seniority: SeniorityLevel = Field(
        default=SeniorityLevel.OTHER, description="Inferred seniority level"
    )
    description_plain: str = Field(default="", description="Plain-text description")
    salary_min: float | None = Field(default=None, description="Salary range lower bound")
    salary_max: float | None = Field(default=None, description="Salary range upper bound")
    salary_currency: str | None = Field(default=None, description="ISO currency code")

    tags: list[str] = Field(default_factory=list, description="Extracted skill / domain tags")

    # ── Extended normalization fields ─────────────────────────────
    title_family: str | None = Field(default=None, description="Canonical title family (COO, VP_OPERATIONS, etc.)")
    industry_family: IndustryFamily = Field(default=IndustryFamily.OTHER, description="Industry classification")
    job_function_family: JobFunctionFamily = Field(default=JobFunctionFamily.OTHER, description="Job function classification")
    scope_level: ScopeLevel = Field(default=ScopeLevel.UNKNOWN, description="Operational scope")
    is_software_heavy: bool = Field(default=False, description="True if role is dominated by software signals")
    is_gtm_heavy: bool = Field(default=False, description="True if role is dominated by GTM/sales signals")
    is_semiconductor_like: bool = Field(default=False, description="True if posting has semiconductor/industrial signals")

    posted_at: datetime | None = Field(default=None, description="Original publication date")
    normalized_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When normalization occurred",
    )

    @model_validator(mode="after")
    def _validate_salary_range(self) -> NormalizedJobPosting:
        """Ensure salary_min <= salary_max when both are present."""
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            msg = f"salary_min ({self.salary_min}) must not exceed salary_max ({self.salary_max})"
            raise ValueError(msg)
        return self
