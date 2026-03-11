"""Exec Radar dashboard — server-rendered Jinja2 UI.

A lightweight FastAPI sub-application that renders a dashboard page
using the existing ``/health`` and ``/jobs`` API endpoints.  Mounted
on the main application at ``/dashboard``.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError

from apps.dashboard.preferences_store import PreferenceStore
from packages.db.profile_repository import (
    activate_profile,
    create_profile,
    export_profile_to_yaml,
    get_active_profile,
    get_profile_by_id,
    import_profile_from_yaml,
    list_profiles,
    resolve_active_target_profile,
    seed_profiles_from_directory,
    suspend_profile,
    unsuspend_profile,
    update_profile,
)
from packages.db.profile_session import get_session as _profiles_session
from packages.pipeline import run_pipeline
from packages.schemas.target_profile import TargetProfile
from packages.services import (
    AVAILABLE_COLLECTORS,
    build_pipeline_components,
    describe_collector,
)
from packages.source_sets import source_set_names
from packages.version import __version__

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parent


def _static_hash() -> str:
    """Return a short hash of the static assets for cache-busting."""
    import hashlib

    h = hashlib.md5(usedforsecurity=False)
    for name in ("app.js", "style.css"):
        p = _DIR / "static" / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:8]


_STATIC_VERSION = _static_hash()
_PREFS_DB_PATH = Path(
    os.getenv("EXEC_RADAR_DASHBOARD_PREFS_DB", ".data/dashboard_preferences.sqlite3")
)

# Project root for locating example profiles
_PROJECT_ROOT = _DIR.parent.parent
_EXAMPLES_DIR = _PROJECT_ROOT / "examples"


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Seed example profiles into the DB on startup if missing."""
    session = await _profiles_session()
    async with session:
        count = await seed_profiles_from_directory(session, _EXAMPLES_DIR)
        if count:
            await session.commit()
            logger.info("Auto-seeded %d profile(s) from %s", count, _EXAMPLES_DIR)
    yield


dashboard_app = FastAPI(
    title="Exec Radar Dashboard",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=_lifespan,
)

dashboard_app.mount(
    "/static",
    StaticFiles(directory=_DIR / "static"),
    name="dashboard_static",
)

templates = Jinja2Templates(directory=_DIR / "templates")
templates.env.globals["static_version"] = _STATIC_VERSION
preferences_store = PreferenceStore(_PREFS_DB_PATH)


class PreferencesResponse(BaseModel):
    """Snapshot of persisted dashboard preferences for one user."""

    user_id: str
    favorites: list[str] = Field(default_factory=list)
    dismissed: list[str] = Field(default_factory=list)


class PreferenceToggleRequest(BaseModel):
    """Toggle request payload for a job preference."""

    job_id: str
    action: Literal["favorite", "dismissed"]
    user_id: str = "default"


class PreferenceToggleResponse(BaseModel):
    """Current preference state after toggle."""

    user_id: str
    job_id: str
    favorited: bool
    dismissed: bool


@dashboard_app.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(user_id: str = "default") -> PreferencesResponse:
    """Return persisted favorites / dismissed sets for a user."""
    favorites, dismissed = preferences_store.get_preferences(user_id=user_id)
    return PreferencesResponse(
        user_id=user_id,
        favorites=sorted(favorites),
        dismissed=sorted(dismissed),
    )


@dashboard_app.post("/preferences/toggle", response_model=PreferenceToggleResponse)
async def toggle_preference(payload: PreferenceToggleRequest) -> PreferenceToggleResponse:
    """Toggle one preference on a job and return current state."""
    try:
        favorited, dismissed = preferences_store.toggle(
            user_id=payload.user_id,
            job_id=payload.job_id,
            action=payload.action,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PreferenceToggleResponse(
        user_id=payload.user_id,
        job_id=payload.job_id,
        favorited=favorited,
        dismissed=dismissed,
    )


@dashboard_app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the main dashboard page.

    Fetches health and jobs data from the pipeline in-process
    (no HTTP round-trip needed since we share the same Python process).
    """
    # ── Health check ───────────────────────────────────────
    health_ok = True
    health_version = __version__
    health_error = ""

    # ── Jobs ───────────────────────────────────────────────
    jobs: list = []
    jobs_error = ""
    active_profile_name: str | None = None
    collector_info: dict = {"type": "mock", "label": "Mock", "sources": ["mock"]}
    try:
        session = await _profiles_session()
        async with session:
            active_record = await get_active_profile(session)
            active_profile = await resolve_active_target_profile(session)
            if active_record is not None:
                active_profile_name = active_record.name
        collector, normalizer, ranker = build_pipeline_components(
            profile=active_profile,
        )
        collector_info = describe_collector(collector)
        jobs = await run_pipeline(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
        )
    except Exception as exc:
        logger.exception("Dashboard: failed to load jobs")
        jobs_error = str(exc)

    profile_activated = request.query_params.get("profile_activated") == "1"

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": __version__,
            "health_ok": health_ok,
            "health_version": health_version,
            "health_error": health_error,
            "jobs": jobs,
            "job_count": len(jobs),
            "jobs_error": jobs_error,
            "active_profile_name": active_profile_name,
            "profile_activated": profile_activated,
            "collector_info": collector_info,
            "available_collectors": AVAILABLE_COLLECTORS,
        },
    )


# ---------------------------------------------------------------------------
# Profile management
# ---------------------------------------------------------------------------


def _profile_status(record) -> str:
    if record.is_suspended:
        return "suspended"
    if record.is_active:
        return "active"
    return "inactive"


# ---------------------------------------------------------------------------
# Profile list page
# ---------------------------------------------------------------------------


@dashboard_app.get("/profiles", response_class=HTMLResponse)
async def profiles_list(request: Request) -> HTMLResponse:
    """Render the profiles management page."""
    session = await _profiles_session()
    async with session:
        records = await list_profiles(session)
        profiles = [
            {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "description": r.description,
                "is_active": r.is_active,
                "is_suspended": r.is_suspended,
                "source_type": r.source_type,
                "status": _profile_status(r),
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")
                if r.created_at
                else "",
                "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M")
                if r.updated_at
                else "",
            }
            for r in records
        ]
    return templates.TemplateResponse(
        request,
        "profiles.html",
        {"version": __version__, "profiles": profiles, "error": ""},
    )


# ---------------------------------------------------------------------------
# Create profile (form + handler)
# ---------------------------------------------------------------------------


@dashboard_app.get("/profiles/new", response_class=HTMLResponse)
async def profiles_new_form(request: Request) -> HTMLResponse:
    """Render the create-profile form."""
    return templates.TemplateResponse(
        request,
        "profile_form.html",
        {
            "version": __version__,
            "mode": "create",
            "profile": None,
            "error": "",
            "source_set_names": source_set_names(),
        },
    )


@dashboard_app.post("/profiles/new", response_model=None)
async def profiles_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    preferred_source_set: str = Form(""),
    target_titles: str = Form(""),
    adjacent_titles: str = Form(""),
    excluded_titles: str = Form(""),
    target_seniority: list[str] | None = Form(None),
    acceptable_seniority: list[str] | None = Form(None),
    preferred_remote_policies: list[str] | None = Form(None),
    target_industries: str = Form(""),
    adjacent_industries: str = Form(""),
    preferred_companies: str = Form(""),
    excluded_companies: str = Form(""),
    must_have_keywords: str = Form(""),
    strong_keywords: str = Form(""),
    nice_to_have_keywords: str = Form(""),
    excluded_keywords: str = Form(""),
    required_keywords: str = Form(""),
    preferred_keywords: str = Form(""),
    preferred_scope_keywords: str = Form(""),
    target_locations: str = Form(""),
    target_geographies: str = Form(""),
    weight_title: float = Form(0.25),
    weight_seniority: float = Form(0.15),
    weight_industry: float = Form(0.15),
    weight_scope: float = Form(0.10),
    weight_geography: float = Form(0.10),
    weight_keyword_clusters: float = Form(0.25),
) -> HTMLResponse | RedirectResponse:
    """Handle profile creation."""

    def _split(val: str) -> list[str]:
        return [v.strip() for v in val.split("\n") if v.strip()]

    try:
        profile_data = TargetProfile(
            preferred_source_set=preferred_source_set.strip(),
            target_titles=frozenset(_split(target_titles)),
            adjacent_titles=frozenset(_split(adjacent_titles)),
            excluded_titles=frozenset(_split(excluded_titles)),
            target_seniority=frozenset(target_seniority or []),
            acceptable_seniority=frozenset(acceptable_seniority or []),
            preferred_remote_policies=frozenset(preferred_remote_policies or []),
            target_industries=frozenset(_split(target_industries)),
            adjacent_industries=frozenset(_split(adjacent_industries)),
            preferred_companies=frozenset(_split(preferred_companies)),
            excluded_companies=frozenset(_split(excluded_companies)),
            must_have_keywords=frozenset(_split(must_have_keywords)),
            strong_keywords=frozenset(_split(strong_keywords)),
            nice_to_have_keywords=frozenset(_split(nice_to_have_keywords)),
            excluded_keywords=frozenset(_split(excluded_keywords)),
            required_keywords=frozenset(_split(required_keywords)),
            preferred_keywords=frozenset(_split(preferred_keywords)),
            preferred_scope_keywords=frozenset(_split(preferred_scope_keywords)),
            target_locations=frozenset(_split(target_locations)),
            target_geographies=frozenset(_split(target_geographies)),
            weight_title=weight_title,
            weight_seniority=weight_seniority,
            weight_industry=weight_industry,
            weight_scope=weight_scope,
            weight_geography=weight_geography,
            weight_keyword_clusters=weight_keyword_clusters,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "profile_form.html",
            {
                "version": __version__,
                "mode": "create",
                "profile": None,
                "error": str(exc),
                "source_set_names": source_set_names(),
            },
            status_code=422,
        )

    session = await _profiles_session()
    async with session:
        try:
            await create_profile(
                session,
                name=name,
                description=description,
                source_type="ui",
                profile_data=profile_data,
            )
            await session.commit()
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "profile_form.html",
                {
                    "version": __version__,
                    "mode": "create",
                    "profile": None,
                    "error": str(exc),
                    "source_set_names": source_set_names(),
                },
                status_code=409,
            )

    return RedirectResponse("/dashboard/profiles", status_code=303)


# ---------------------------------------------------------------------------
# Edit profile (form + handler)
# ---------------------------------------------------------------------------


@dashboard_app.get("/profiles/{profile_id}/edit", response_class=HTMLResponse)
async def profiles_edit_form(
    request: Request, profile_id: str
) -> HTMLResponse:
    """Render the edit-profile form."""
    session = await _profiles_session()
    async with session:
        record = await get_profile_by_id(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = json.loads(record.profile_data_json)
        profile_ctx = {
            "id": record.id,
            "name": record.name,
            "description": record.description,
            "data": profile_data,
        }

    return templates.TemplateResponse(
        request,
        "profile_form.html",
        {
            "version": __version__,
            "mode": "edit",
            "profile": profile_ctx,
            "error": "",
            "source_set_names": source_set_names(),
        },
    )


@dashboard_app.post(
    "/profiles/{profile_id}/edit", response_model=None
)
async def profiles_update(
    request: Request,
    profile_id: str,
    name: str = Form(...),
    description: str = Form(""),
    preferred_source_set: str = Form(""),
    target_titles: str = Form(""),
    adjacent_titles: str = Form(""),
    excluded_titles: str = Form(""),
    target_seniority: list[str] | None = Form(None),
    acceptable_seniority: list[str] | None = Form(None),
    preferred_remote_policies: list[str] | None = Form(None),
    target_industries: str = Form(""),
    adjacent_industries: str = Form(""),
    preferred_companies: str = Form(""),
    excluded_companies: str = Form(""),
    must_have_keywords: str = Form(""),
    strong_keywords: str = Form(""),
    nice_to_have_keywords: str = Form(""),
    excluded_keywords: str = Form(""),
    required_keywords: str = Form(""),
    preferred_keywords: str = Form(""),
    preferred_scope_keywords: str = Form(""),
    target_locations: str = Form(""),
    target_geographies: str = Form(""),
    weight_title: float = Form(0.25),
    weight_seniority: float = Form(0.15),
    weight_industry: float = Form(0.15),
    weight_scope: float = Form(0.10),
    weight_geography: float = Form(0.10),
    weight_keyword_clusters: float = Form(0.25),
) -> HTMLResponse | RedirectResponse:
    """Handle profile update."""

    def _split(val: str) -> list[str]:
        return [v.strip() for v in val.split("\n") if v.strip()]

    try:
        profile_data = TargetProfile(
            preferred_source_set=preferred_source_set.strip(),
            target_titles=frozenset(_split(target_titles)),
            adjacent_titles=frozenset(_split(adjacent_titles)),
            excluded_titles=frozenset(_split(excluded_titles)),
            target_seniority=frozenset(target_seniority or []),
            acceptable_seniority=frozenset(acceptable_seniority or []),
            preferred_remote_policies=frozenset(preferred_remote_policies or []),
            target_industries=frozenset(_split(target_industries)),
            adjacent_industries=frozenset(_split(adjacent_industries)),
            preferred_companies=frozenset(_split(preferred_companies)),
            excluded_companies=frozenset(_split(excluded_companies)),
            must_have_keywords=frozenset(_split(must_have_keywords)),
            strong_keywords=frozenset(_split(strong_keywords)),
            nice_to_have_keywords=frozenset(_split(nice_to_have_keywords)),
            excluded_keywords=frozenset(_split(excluded_keywords)),
            required_keywords=frozenset(_split(required_keywords)),
            preferred_keywords=frozenset(_split(preferred_keywords)),
            preferred_scope_keywords=frozenset(_split(preferred_scope_keywords)),
            target_locations=frozenset(_split(target_locations)),
            target_geographies=frozenset(_split(target_geographies)),
            weight_title=weight_title,
            weight_seniority=weight_seniority,
            weight_industry=weight_industry,
            weight_scope=weight_scope,
            weight_geography=weight_geography,
            weight_keyword_clusters=weight_keyword_clusters,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "profile_form.html",
            {
                "version": __version__,
                "mode": "edit",
                "profile": {"id": profile_id, "name": name, "description": description},
                "error": str(exc),
                "source_set_names": source_set_names(),
            },
            status_code=422,
        )

    session = await _profiles_session()
    async with session:
        await update_profile(
            session,
            profile_id,
            name=name,
            description=description,
            profile_data=profile_data,
        )
        await session.commit()

    return RedirectResponse("/dashboard/profiles", status_code=303)


# ---------------------------------------------------------------------------
# Profile actions (activate / suspend / unsuspend)
# ---------------------------------------------------------------------------


@dashboard_app.post("/profiles/{profile_id}/activate")
async def profiles_activate(profile_id: str) -> RedirectResponse:
    session = await _profiles_session()
    async with session:
        try:
            await activate_profile(session, profile_id)
            await session.commit()
        except ValueError:
            return RedirectResponse("/dashboard/profiles", status_code=303)
    return RedirectResponse("/dashboard/?profile_activated=1", status_code=303)


@dashboard_app.post("/profiles/{profile_id}/suspend")
async def profiles_suspend(profile_id: str) -> RedirectResponse:
    session = await _profiles_session()
    async with session:
        await suspend_profile(session, profile_id)
        await session.commit()
    return RedirectResponse("/dashboard/profiles", status_code=303)


@dashboard_app.post("/profiles/{profile_id}/unsuspend")
async def profiles_unsuspend(profile_id: str) -> RedirectResponse:
    session = await _profiles_session()
    async with session:
        await unsuspend_profile(session, profile_id)
        await session.commit()
    return RedirectResponse("/dashboard/profiles", status_code=303)


# ---------------------------------------------------------------------------
# Profile detail page
# ---------------------------------------------------------------------------


@dashboard_app.get(
    "/profiles/{profile_id}", response_class=HTMLResponse
)
async def profiles_detail(
    request: Request, profile_id: str
) -> HTMLResponse:
    """Render a profile detail page."""
    session = await _profiles_session()
    async with session:
        record = await get_profile_by_id(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_data = json.loads(record.profile_data_json)
        profile_ctx = {
            "id": record.id,
            "name": record.name,
            "slug": record.slug,
            "description": record.description,
            "is_active": record.is_active,
            "is_suspended": record.is_suspended,
            "source_type": record.source_type,
            "status": _profile_status(record),
            "data": profile_data,
            "created_at": record.created_at.strftime("%Y-%m-%d %H:%M")
            if record.created_at
            else "",
            "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M")
            if record.updated_at
            else "",
        }

    return templates.TemplateResponse(
        request,
        "profile_detail.html",
        {"version": __version__, "profile": profile_ctx},
    )


# ---------------------------------------------------------------------------
# Export profile as YAML
# ---------------------------------------------------------------------------


@dashboard_app.get("/profiles/{profile_id}/export")
async def profiles_export(profile_id: str) -> Response:
    """Download a profile as YAML."""
    session = await _profiles_session()
    async with session:
        record = await get_profile_by_id(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")

        yaml_content = export_profile_to_yaml(record)
        filename = f"{record.slug}.yaml"

    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


# ---------------------------------------------------------------------------
# Upload / import YAML profile
# ---------------------------------------------------------------------------


@dashboard_app.get("/profiles/upload/form", response_class=HTMLResponse)
async def profiles_upload_form(request: Request) -> HTMLResponse:
    """Render the YAML upload form."""
    return templates.TemplateResponse(
        request,
        "profile_upload.html",
        {"version": __version__, "error": ""},
    )


@dashboard_app.post("/profiles/upload/form", response_model=None)
async def profiles_upload(
    request: Request,
    file: UploadFile,
    name: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    """Handle YAML file upload."""
    content = await file.read()
    try:
        yaml_content = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        return templates.TemplateResponse(
            request,
            "profile_upload.html",
            {"version": __version__, "error": f"File is not valid UTF-8: {exc}"},
            status_code=422,
        )

    profile_name = name or (
        (file.filename or "Uploaded Profile")
        .removesuffix(".yaml")
        .removesuffix(".yml")
    )

    session = await _profiles_session()
    async with session:
        try:
            await import_profile_from_yaml(
                session,
                yaml_content=yaml_content,
                name=profile_name,
                description=f"Uploaded from {file.filename or 'file'}",
                source_type="upload",
            )
            await session.commit()
        except (ValueError, ValidationError) as exc:
            return templates.TemplateResponse(
                request,
                "profile_upload.html",
                {
                    "version": __version__,
                    "error": f"Import failed: {exc}",
                },
                status_code=422,
            )

    return RedirectResponse("/dashboard/profiles", status_code=303)


# ---------------------------------------------------------------------------
# Multi-profile comparison
# ---------------------------------------------------------------------------


@dashboard_app.get("/compare", response_class=HTMLResponse)
async def compare_profiles(request: Request) -> HTMLResponse:
    """Render comparison page — pick two profiles, see score differences."""
    session = await _profiles_session()
    async with session:
        records = await list_profiles(session)
        profiles_meta = [
            {"id": r.id, "name": r.name, "is_active": r.is_active}
            for r in records
            if not r.is_suspended
        ]

    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "version": __version__,
            "profiles": profiles_meta,
            "results": None,
            "error": "",
        },
    )


@dashboard_app.post("/compare", response_class=HTMLResponse)
async def compare_profiles_run(
    request: Request,
    profile_a: str = Form(...),
    profile_b: str = Form(...),
    max_jobs: int = Form(30),
) -> HTMLResponse:
    """Run the same jobs through two profiles and show side-by-side scores."""
    from packages.db.profile_repository import _json_to_profile
    from packages.rankers.rule_based_ranker import RuleBasedRanker

    session = await _profiles_session()
    async with session:
        records = await list_profiles(session)
        profiles_meta = [
            {"id": r.id, "name": r.name, "is_active": r.is_active}
            for r in records
            if not r.is_suspended
        ]

        rec_a = await get_profile_by_id(session, profile_a)
        rec_b = await get_profile_by_id(session, profile_b)

    if rec_a is None or rec_b is None:
        return templates.TemplateResponse(
            request,
            "compare.html",
            {
                "version": __version__,
                "profiles": profiles_meta,
                "results": None,
                "error": "One or both profiles not found.",
            },
        )

    tp_a = _json_to_profile(rec_a.profile_data_json)
    tp_b = _json_to_profile(rec_b.profile_data_json)

    # Collect jobs once with profile A's source set
    collector_a, normalizer, ranker_a = build_pipeline_components(profile=tp_a)
    raw_postings = await collector_a.collect()
    normalized = [normalizer.normalize(raw) for raw in raw_postings]

    # Score with both profiles
    ranker_b = RuleBasedRanker(profile=tp_b)
    scores_a = {s.job_id: s for s in ranker_a.score_batch(normalized)}
    scores_b = {s.job_id: s for s in ranker_b.score_batch(normalized)}

    rows = []
    for job in normalized:
        sa = scores_a.get(job.id)
        sb = scores_b.get(job.id)
        if sa and sb:
            rows.append({
                "title": job.title,
                "company": job.company or "",
                "location": job.location or "",
                "score_a": round(sa.overall, 4),
                "score_b": round(sb.overall, 4),
                "delta": round(sa.overall - sb.overall, 4),
                "dims_a": sa.dimension_scores,
                "dims_b": sb.dimension_scores,
            })

    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    rows = rows[:max_jobs]

    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "version": __version__,
            "profiles": profiles_meta,
            "results": rows,
            "name_a": rec_a.name,
            "name_b": rec_b.name,
            "selected_a": profile_a,
            "selected_b": profile_b,
            "error": "",
        },
    )
