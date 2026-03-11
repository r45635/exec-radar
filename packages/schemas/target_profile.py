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

    # ── Source set preference ────────────────────────────────────
    preferred_source_set: str = Field(
        default="",
        description=(
            "Named source set to use when collecting jobs for this "
            "profile (e.g. 'semiconductor_exec'). Empty means default."
        ),
    )

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
    adjacent_titles: frozenset[str] = Field(
        default=frozenset(
            {
                "vp manufacturing",
                "vice president manufacturing",
                "svp manufacturing",
                "head of manufacturing",
                "director of manufacturing",
                "vp supply chain",
                "head of supply chain",
                "vp industrial operations",
                "head of industrial operations",
                "plant director",
                "general manager operations",
                "vp operational excellence",
                "head of operational excellence",
            }
        ),
        description=(
            "Related titles that are not the primary target but still "
            "interesting (partial title score)."
        ),
    )
    excluded_titles: frozenset[str] = Field(
        default=frozenset(
            {
                "intern",
                "junior",
                "entry level",
                "associate",
                "assistant",
            }
        ),
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
    target_geographies: frozenset[str] = Field(
        default=frozenset(
            {
                "france",
                "germany",
                "switzerland",
                "europe",
                "united states",
                "usa",
            }
        ),
        description=(
            "Broader geographic regions or countries "
            "(matched against location text)."
        ),
    )

    # ── Industry preferences ──────────────────────────────────────
    target_industries: frozenset[str] = Field(
        default=frozenset(
            {
                "semiconductor",
                "electronics",
                "automotive",
                "industrial manufacturing",
                "advanced manufacturing",
                "aerospace",
            }
        ),
        description="Target industries — matched against tags and description.",
    )
    adjacent_industries: frozenset[str] = Field(
        default=frozenset(
            {
                "energy",
                "chemicals",
                "defense",
                "medical devices",
                "heavy industry",
                "logistics",
            }
        ),
        description=(
            "Related industries that are not primary targets "
            "but still relevant (partial score)."
        ),
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

    # ── Keywords (tiered) ─────────────────────────────────────────
    must_have_keywords: frozenset[str] = Field(
        default=frozenset(
            {
                "operations",
                "manufacturing",
                "industrial",
            }
        ),
        description=(
            "Deal-breaker keywords — a posting missing ALL of these "
            "is heavily penalized."
        ),
    )
    strong_keywords: frozenset[str] = Field(
        default=frozenset(
            {
                "supply chain",
                "P&L",
                "transformation",
                "continuous improvement",
                "lean",
                "six sigma",
                "operational excellence",
                "quality",
                "production",
                "plant",
            }
        ),
        description="High-value keywords (significant score contribution).",
    )
    nice_to_have_keywords: frozenset[str] = Field(
        default=frozenset(
            {
                "change management",
                "strategy",
                "digital transformation",
                "ERP",
                "SAP",
                "capex",
                "scalability",
                "KPI",
                "OKR",
            }
        ),
        description="Bonus keywords (small uplift).",
    )
    excluded_keywords: frozenset[str] = Field(
        default=frozenset(
            {
                "entry level",
                "unpaid",
                "internship",
            }
        ),
        description="Keywords that signal an irrelevant posting.",
    )

    # ── Scope keywords ────────────────────────────────────────────
    preferred_scope_keywords: frozenset[str] = Field(
        default=frozenset(
            {
                "global",
                "multi-site",
                "regional",
                "international",
                "p&l responsibility",
                "budget",
                "headcount",
                "direct reports",
            }
        ),
        description=(
            "Scope indicators (multi-site, global, P&L size) "
            "that boost the scope dimension."
        ),
    )

    # ── Legacy aliases (backward compat) ──────────────────────────
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

    # ── Scoring weights (6 dimensions) ────────────────────────────
    weight_title: float = Field(
        default=0.25, ge=0.0, le=1.0,
        description="Title dimension weight",
    )
    weight_seniority: float = Field(
        default=0.15, ge=0.0, le=1.0,
        description="Seniority dimension weight",
    )
    weight_industry: float = Field(
        default=0.15, ge=0.0, le=1.0,
        description="Industry dimension weight",
    )
    weight_scope: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="Scope dimension weight",
    )
    weight_geography: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="Geography / location dimension weight",
    )
    weight_keyword_clusters: float = Field(
        default=0.25, ge=0.0, le=1.0,
        description="Keyword-cluster dimension weight",
    )

    # Legacy weight aliases — kept so old YAML files don't break
    weight_location: float = Field(
        default=0.15, ge=0.0, le=1.0,
        description="(legacy) Location dimension weight",
    )
    weight_skills: float = Field(
        default=0.25, ge=0.0, le=1.0,
        description="(legacy) Skills dimension weight",
    )
