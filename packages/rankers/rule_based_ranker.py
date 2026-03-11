"""Rule-based ranker — deterministic, explainable scoring engine.

Scores each posting against a :class:`TargetProfile` across six
dimensions: title, seniority, industry, scope, geography, and
keyword-clusters.  Produces a :class:`FitScore` with per-dimension
breakdowns and structured ``why_matched`` / ``why_penalized`` /
``red_flags`` lists.
"""

from __future__ import annotations

from packages.normalizers.title_families import (
    NON_OPS_CSUITE,
    OPERATIONS_FAMILIES,
    resolve_title_family,
)
from packages.rankers.base import BaseRanker
from packages.rankers.keyword_clusters import (
    aggregate_cluster_score,
    score_clusters,
)
from packages.schemas.fit_score import FitScore
from packages.schemas.normalized_job import (
    NormalizedJobPosting,
    RemotePolicy,
    SeniorityLevel,
)
from packages.schemas.target_profile import TargetProfile


class RuleBasedRanker(BaseRanker):
    """A deterministic, rule-based ranker.

    Scores each posting against a configurable :class:`TargetProfile`.
    If no profile is supplied, the built-in defaults are used.

    Designed as an explainable baseline; future iterations will use
    embeddings and LLM-based evaluation.
    """

    def __init__(self, profile: TargetProfile | None = None) -> None:
        self._profile = profile or TargetProfile()

    @property
    def profile(self) -> TargetProfile:
        """The active target profile."""
        return self._profile

    def score(self, job: NormalizedJobPosting) -> FitScore:
        """Score a posting against the target executive profile.

        Returns a :class:`FitScore` with legacy dimension fields
        **and** the new ``dimension_scores``, ``why_matched``,
        ``why_penalized``, and ``red_flags`` structures.
        """
        p = self._profile
        why_matched: list[str] = []
        why_penalized: list[str] = []
        red_flags: list[str] = []

        # ── 1. Title ──────────────────────────────────────────────
        title_score, title_notes = self._score_title(
            job.title, p.target_titles, p.adjacent_titles, p.excluded_titles,
        )
        why_matched.extend(n for n in title_notes if not n.startswith("!"))
        why_penalized.extend(n[1:] for n in title_notes if n.startswith("!"))

        # ── 2. Seniority ─────────────────────────────────────────
        seniority_score = self._score_seniority(
            job.seniority, p.target_seniority, p.acceptable_seniority,
        )
        if seniority_score >= 0.8:
            why_matched.append("Seniority aligns")
        elif seniority_score <= 0.2:
            why_penalized.append("Seniority too junior or unrecognised")
            red_flags.append("Seniority mismatch")

        # ── 3. Industry ──────────────────────────────────────────
        industry_score = self._score_industry(
            job.tags,
            job.description_plain,
            p.target_industries,
            p.adjacent_industries,
        )
        if industry_score >= 0.6:
            why_matched.append("Strong industry fit")
        elif industry_score >= 0.3:
            why_matched.append("Adjacent industry")

        # ── 4. Scope ─────────────────────────────────────────────
        scope_score = self._score_scope(
            job.description_plain, p.preferred_scope_keywords,
        )
        if scope_score >= 0.4:
            why_matched.append("Good scope indicators")

        # ── 5. Geography ─────────────────────────────────────────
        geo_score = self._score_geography(
            job.remote_policy,
            p.preferred_remote_policies,
            job.location,
            p.target_locations,
            p.target_geographies,
        )
        if geo_score >= 0.8:
            why_matched.append("Location / remote fit")

        # ── 6. Keyword clusters ──────────────────────────────────
        cluster_scores = score_clusters(job.tags, job.description_plain)
        kw_cluster_score = aggregate_cluster_score(cluster_scores)
        if kw_cluster_score >= 0.15:
            top = sorted(cluster_scores, key=cluster_scores.get, reverse=True)  # type: ignore[arg-type]
            why_matched.append(f"Keyword cluster: {top[0]}")

        # -- Fabless/foundry/OSAT cluster explainability -----------
        ffo_score = cluster_scores.get("fabless_foundry_osat", 0.0)
        if ffo_score >= 0.10:
            why_matched.append(
                f"Fabless/foundry/OSAT signals ({ffo_score:.0%})"
            )

        # ── Tiered keyword check ─────────────────────────────────
        combined_text = (
            " ".join(job.tags).lower() + " " + job.description_plain.lower()
        )
        if p.must_have_keywords:
            must_hits = sum(
                1 for kw in p.must_have_keywords if kw.lower() in combined_text
            )
            if must_hits == 0:
                why_penalized.append("Missing all must-have keywords")
                red_flags.append("No must-have keyword found")

        if p.excluded_keywords:
            excl_hits = [
                kw for kw in p.excluded_keywords if kw.lower() in combined_text
            ]
            if excl_hits:
                why_penalized.append(
                    f"Excluded keywords: {', '.join(excl_hits)}"
                )
                red_flags.append("Contains excluded keywords")

        # ── Legacy skills score (backward compat) ─────────────────
        skills_score = self._score_skills(
            job.tags,
            p.required_keywords,
            p.preferred_keywords,
            p.excluded_keywords,
            p.target_industries,
        )

        # ── Weighted aggregate ────────────────────────────────────
        dim = {
            "title": title_score,
            "seniority": seniority_score,
            "industry": industry_score,
            "scope": scope_score,
            "geography": geo_score,
            "keyword_clusters": kw_cluster_score,
        }
        overall = (
            p.weight_title * title_score
            + p.weight_seniority * seniority_score
            + p.weight_industry * industry_score
            + p.weight_scope * scope_score
            + p.weight_geography * geo_score
            + p.weight_keyword_clusters * kw_cluster_score
        )

        # ── Post-scoring penalties ────────────────────────────────
        overall = self._apply_penalties(
            overall,
            job,
            p,
            combined_text,
            title_score,
            scope_score,
            cluster_scores,
            why_penalized,
            red_flags,
        )

        # ── Company adjustments ───────────────────────────────────
        company_lower = (job.company or "").lower().strip()
        if company_lower and p.excluded_companies:
            if company_lower in {c.lower() for c in p.excluded_companies}:
                overall *= 0.1
                why_penalized.append("Excluded company")
                red_flags.append("Excluded company")
        if company_lower and p.preferred_companies:
            if company_lower in {c.lower() for c in p.preferred_companies}:
                overall += 0.1
                why_matched.append("Preferred company")

        overall = max(0.0, min(1.0, overall))

        # ── Build explanation string ──────────────────────────────
        parts: list[str] = []
        if why_matched:
            parts.append("Matched: " + "; ".join(why_matched))
        if why_penalized:
            parts.append("Penalized: " + "; ".join(why_penalized))
        if red_flags:
            parts.append("Red flags: " + "; ".join(red_flags))
        explanation = " | ".join(parts) if parts else "Low overall fit"

        return FitScore(
            job_id=job.id,
            overall=round(overall, 4),
            title_match=round(max(0.0, min(1.0, title_score)), 4),
            seniority_match=round(seniority_score, 4),
            location_match=round(max(0.0, min(1.0, geo_score)), 4),
            skills_match=round(max(0.0, min(1.0, skills_score)), 4),
            explanation=explanation,
            dimension_scores={k: round(v, 4) for k, v in dim.items()},
            why_matched=why_matched,
            why_penalized=why_penalized,
            red_flags=red_flags,
        )

    # ------------------------------------------------------------------
    # Post-scoring penalty engine
    # ------------------------------------------------------------------

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

    _INDUSTRIAL_SIGNALS = frozenset({
        "manufacturing", "supply chain", "industrialization", "quality",
        "production", "operations", "lean", "six sigma", "procurement",
        "logistics", "npi", "ramp", "fab", "foundry", "osat", "assembly",
        "test", "yield", "reliability", "warehouse", "plant",
    })

    @staticmethod
    def _apply_penalties(
        overall: float,
        job: NormalizedJobPosting,
        profile: TargetProfile,
        combined_text: str,
        title_score: float,
        scope_score: float,
        cluster_scores: dict[str, float],
        why_penalized: list[str],
        red_flags: list[str],
    ) -> float:
        """Apply post-scoring penalties for noise reduction.

        Mutates *why_penalized* and *red_flags* in place.
        Returns the adjusted overall score.
        """
        # -- 1. Software-heavy penalty ----------------------------
        sw_hits = sum(
            1 for kw in RuleBasedRanker._SOFTWARE_SIGNALS
            if kw in combined_text
        )
        if sw_hits >= 3:
            overall *= 0.50
            why_penalized.append(
                f"Software-heavy role ({sw_hits} software signals)"
            )
            red_flags.append("Software-heavy role")
        elif sw_hits >= 2:
            overall *= 0.75
            why_penalized.append("Some software signals detected")

        # -- 2. GTM / business-only penalty -----------------------
        gtm_hits = sum(
            1 for kw in RuleBasedRanker._GTM_SIGNALS
            if kw in combined_text
        )
        if gtm_hits >= 2:
            overall *= 0.50
            why_penalized.append(
                f"Business/GTM-heavy role ({gtm_hits} GTM signals)"
            )
            red_flags.append("GTM / business-only role")
        elif gtm_hits == 1:
            overall *= 0.80
            why_penalized.append("GTM signal detected")

        # -- 3. Ops title but weak industrial scope ---------------
        #    Title looks right but no manufacturing/SC/industrial evidence
        if title_score >= 0.5:
            ind_hits = sum(
                1 for kw in RuleBasedRanker._INDUSTRIAL_SIGNALS
                if kw in combined_text
            )
            if ind_hits == 0:
                overall *= 0.55
                why_penalized.append(
                    "Ops title but no industrial/manufacturing evidence"
                )
                red_flags.append("Misleading operations title")
            elif ind_hits <= 1 and scope_score < 0.15:
                overall *= 0.75
                why_penalized.append(
                    "Weak industrial scope for operations title"
                )

        # -- 4. Too-junior hard penalty ---------------------------
        title_lower = job.title.lower()
        junior_markers = {"intern", "junior", "entry level", "trainee",
                          "apprentice", "assistant"}
        if any(m in title_lower for m in junior_markers):
            if job.seniority == SeniorityLevel.OTHER:
                overall *= 0.30
                why_penalized.append("Junior-level role")
                red_flags.append("Too junior")

        # -- 5. Narrow single-site/plant when exec scope wanted ---
        #    Profile has broad scope keywords but job is narrow
        narrow_markers = {"single site", "one plant", "local plant",
                          "site-level", "plant-level"}
        has_broad_scope = any(
            kw in {"global operations", "multi-site",
                    "international footprint", "cross-functional leadership"}
            for kw in (k.lower() for k in profile.preferred_scope_keywords)
        )
        if has_broad_scope:
            is_narrow = any(m in combined_text for m in narrow_markers)
            # Also check: title says Plant Director + no global/multi-site
            if (
                is_narrow
                or (
                    "plant director" in title_lower
                    and "multi-site" not in combined_text
                    and "global" not in combined_text
                )
            ):
                overall *= 0.70
                why_penalized.append(
                    "Narrow scope (single-site/plant) vs. exec profile"
                )

        return overall

    # ------------------------------------------------------------------
    # Dimension scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_title(
        title: str,
        target_titles: frozenset[str],
        adjacent_titles: frozenset[str],
        excluded_titles: frozenset[str],
    ) -> tuple[float, list[str]]:
        """Score title with family-aware matching.

        Returns (score, notes) where notes prefixed with ``!`` are
        negative.
        """
        lower = title.lower().strip()
        notes: list[str] = []

        # Excluded titles always lose
        if excluded_titles:
            for ex in excluded_titles:
                if ex in lower or lower in ex:
                    notes.append("!Title excluded by profile")
                    return 0.0, notes

        # Exact target match
        if lower in target_titles:
            notes.append("Strong title match")
            return 1.0, notes

        # Substring / partial target match
        for target in target_titles:
            if target in lower or lower in target:
                notes.append("Strong title match")
                return 1.0, notes

        # Adjacent title match
        for adj in adjacent_titles:
            if adj in lower or lower in adj:
                notes.append("Adjacent title match")
                return 0.6, notes

        # Title-family matching
        family = resolve_title_family(title)
        if family:
            if family in OPERATIONS_FAMILIES:
                notes.append(f"Ops-family title ({family})")
                return 0.5, notes
            if family in NON_OPS_CSUITE:
                notes.append(f"!Non-ops C-suite ({family})")
                return 0.15, notes
            notes.append(f"Recognised title family ({family})")
            return 0.3, notes

        return 0.0, notes

    @staticmethod
    def _score_seniority(
        level: SeniorityLevel,
        target: frozenset[SeniorityLevel],
        acceptable: frozenset[SeniorityLevel],
    ) -> float:
        """Return 1.0 for target-level, 0.6 for acceptable, 0.2 otherwise."""
        if level in target:
            return 1.0
        if level in acceptable:
            return 0.6
        return 0.2

    @staticmethod
    def _score_industry(
        tags: list[str],
        description: str,
        target_industries: frozenset[str],
        adjacent_industries: frozenset[str],
    ) -> float:
        """Score industry fit from tags and description."""
        combined = " ".join(tags).lower() + " " + description.lower()
        target_lower = {i.lower() for i in target_industries}
        adjacent_lower = {i.lower() for i in adjacent_industries}

        target_hits = sum(1 for ind in target_lower if ind in combined)
        adjacent_hits = sum(1 for ind in adjacent_lower if ind in combined)

        score = 0.0
        if target_lower:
            score += 0.7 * min(1.0, target_hits / max(1, len(target_lower)))
        if adjacent_lower:
            score += 0.3 * min(1.0, adjacent_hits / max(1, len(adjacent_lower)))
        return min(1.0, score)

    @staticmethod
    def _score_scope(
        description: str,
        scope_keywords: frozenset[str],
    ) -> float:
        """Score executive scope from description text."""
        if not scope_keywords:
            return 0.5  # neutral when unconfigured
        desc_lower = description.lower()
        hits = sum(1 for kw in scope_keywords if kw.lower() in desc_lower)
        return min(1.0, hits / max(1, len(scope_keywords)))

    @staticmethod
    def _score_geography(
        remote_policy: RemotePolicy,
        preferred: frozenset[RemotePolicy],
        location: str | None,
        target_locations: frozenset[str],
        target_geographies: frozenset[str],
    ) -> float:
        """Score geography / remote-policy fit."""
        if remote_policy in preferred:
            return 1.0
        if location:
            loc_lower = location.lower()
            if target_locations and any(
                tl.lower() in loc_lower for tl in target_locations
            ):
                return 0.8
            if target_geographies and any(
                tg.lower() in loc_lower for tg in target_geographies
            ):
                return 0.7
        if remote_policy == RemotePolicy.UNKNOWN:
            return 0.5
        return 0.3

    @staticmethod
    def _score_skills(
        tags: list[str],
        required: frozenset[str],
        preferred: frozenset[str],
        excluded: frozenset[str],
        industries: frozenset[str],
    ) -> float:
        """Compute keyword overlap (legacy, kept for backward compat)."""
        if not tags:
            return 0.0

        tag_set = {t.lower() for t in tags}
        required_lower = {s.lower() for s in required}
        preferred_lower = {s.lower() for s in preferred}
        excluded_lower = {s.lower() for s in excluded}
        industries_lower = {s.lower() for s in industries}

        if required_lower:
            overlap = tag_set & required_lower
            base = len(overlap) / len(required_lower)
        else:
            base = 0.0

        if preferred_lower:
            pref_overlap = tag_set & preferred_lower
            base += 0.2 * (len(pref_overlap) / len(preferred_lower))

        if industries_lower:
            ind_overlap = tag_set & industries_lower
            base += 0.15 * (len(ind_overlap) / len(industries_lower))

        if excluded_lower and (tag_set & excluded_lower):
            base -= 0.3

        return base
