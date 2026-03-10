"""Target profile schema — defines what the user is looking for."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from packages.schemas.normalized_job import RemotePolicy, SeniorityLevel


class TargetProfile(BaseModel):
    """Configurable executive target profile used by rankers.

    Describes the ideal role the user is pursuing.  Rankers compare
    each :class:`NormalizedJobPosting` against this profile to produce
    a :class:`FitScore`.

    All fields have sensible defaults so a bare ``TargetProfile()``
    works out of the box, but callers are encouraged to load a
    customized profile from YAML/JSON.
    """

    model_config = ConfigDict(frozen=True)

    # ── Title preferences ──────────────────────────────────────────
    target_titles: frozenset[str] = Field(
        default=frozenset(
            {
                "chief operating officer",
                "coo",
                "vp of operations",
                "vice president of operations",
                "svp operations",
                "head of operations",
                "director of operations",
                "head of business transformation",
            }
        ),
        description="Desired job titles (case-insensitive match).",
    )
    excluded_titles: frozenset[str] = Field(
        default=frozenset(),
        description="Titles to penalize or exclude outright.",
    )

    # ── Seniority preferences ─────────────────────────────────────
    target_seniority: frozenset[SeniorityLevel] = Field(
        default=frozenset(
            {
                SeniorityLevel.C_LEVEL,
                SeniorityLevel.SVP,
                SeniorityLevel.VP,
            }
        ),
        description="Desired seniority levels (full score).",
    )
    acceptable_seniority: frozenset[SeniorityLevel] = Field(
        default=frozenset(
            {
                SeniorityLevel.DIRECTOR,
                SeniorityLevel.HEAD,
            }
        ),
        description="Acceptable seniority levels (partial score).",
    )

    # ── Location / remote preferences ─────────────────────────────
    preferred_remote_policies: frozenset[RemotePolicy] = Field(
        default=frozenset(
            {
                RemotePolicy.REMOTE,
                RemotePolicy.HYBRID,
            }
        ),
        description="Preferred remote-work policies.",
    )
    target_locations: frozenset[str] = Field(
        default=frozenset(),
        description="Preferred geographic locations (case-insensitive substring match).",
    )

    # ── Industry preferences ──────────────────────────────────────
    target_industries: frozenset[str] = Field(
        default=frozenset(),
        description="Target industries — matched against job tags as a bonus.",
    )

    # ── Company preferences ───────────────────────────────────────
    preferred_companies: frozenset[str] = Field(
        default=frozenset(),
        description="Companies to boost when matched (case-insensitive).",
    )
    excluded_companies: frozenset[str] = Field(
        default=frozenset(),
        description="Companies to penalize when matched (case-insensitive).",
    )

    # ── Skills / keywords ─────────────────────────────────────────
    required_keywords: frozenset[str] = Field(
        default=frozenset(
            {
                "operations",
                "supply chain",
                "logistics",
                "strategy",
                "transformation",
                "change management",
                "P&L",
                "manufacturing",
            }
        ),
        description="Domain keywords the ideal posting should contain.",
    )
    preferred_keywords: frozenset[str] = Field(
        default=frozenset(),
        description="Nice-to-have keywords (bonus, not required).",
    )
    excluded_keywords: frozenset[str] = Field(
        default=frozenset(),
        description="Keywords that signal an irrelevant posting.",
    )

    # ── Scoring weights ───────────────────────────────────────────
    weight_title: float = Field(default=0.35, ge=0.0, le=1.0, description="Title dimension weight")
    weight_seniority: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Seniority dimension weight"
    )
    weight_location: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Location dimension weight"
    )
    weight_skills: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Skills dimension weight"
    )
