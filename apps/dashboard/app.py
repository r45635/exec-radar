"""Exec Radar dashboard — server-rendered Jinja2 UI.

A lightweight FastAPI sub-application that renders a dashboard page
using the existing ``/health`` and ``/jobs`` API endpoints.  Mounted
on the main application at ``/dashboard``.
"""

from __future__ import annotations

import json
import logging
import os
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
    get_profile_by_id,
    import_profile_from_yaml,
    list_profiles,
    resolve_active_target_profile,
    suspend_profile,
    unsuspend_profile,
    update_profile,
)
from packages.db.profile_session import get_session as _profiles_session
from packages.pipeline import run_pipeline
from packages.schemas.target_profile import TargetProfile
from packages.services import build_pipeline_components
from packages.version import __version__

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parent
_PREFS_DB_PATH = Path(
    os.getenv("EXEC_RADAR_DASHBOARD_PREFS_DB", ".data/dashboard_preferences.sqlite3")
)

dashboard_app = FastAPI(
    title="Exec Radar Dashboard",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

dashboard_app.mount(
    "/static",
    StaticFiles(directory=_DIR / "static"),
    name="dashboard_static",
)

templates = Jinja2Templates(directory=_DIR / "templates")
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
    try:
        session = await _profiles_session()
        async with session:
            active_profile = await resolve_active_target_profile(session)
        collector, normalizer, ranker = build_pipeline_components(
            profile=active_profile,
        )
        jobs = await run_pipeline(
            collector=collector,
            normalizer=normalizer,
            ranker=ranker,
        )
    except Exception as exc:
        logger.exception("Dashboard: failed to load jobs")
        jobs_error = str(exc)

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
        {"version": __version__, "mode": "create", "profile": None, "error": ""},
    )


@dashboard_app.post("/profiles/new", response_model=None)
async def profiles_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    target_titles: str = Form(""),
    adjacent_titles: str = Form(""),
    excluded_titles: str = Form(""),
    target_industries: str = Form(""),
    adjacent_industries: str = Form(""),
    must_have_keywords: str = Form(""),
    strong_keywords: str = Form(""),
    nice_to_have_keywords: str = Form(""),
    excluded_keywords: str = Form(""),
    preferred_scope_keywords: str = Form(""),
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
            target_titles=frozenset(_split(target_titles)),
            adjacent_titles=frozenset(_split(adjacent_titles)),
            excluded_titles=frozenset(_split(excluded_titles)),
            target_industries=frozenset(_split(target_industries)),
            adjacent_industries=frozenset(_split(adjacent_industries)),
            must_have_keywords=frozenset(_split(must_have_keywords)),
            strong_keywords=frozenset(_split(strong_keywords)),
            nice_to_have_keywords=frozenset(_split(nice_to_have_keywords)),
            excluded_keywords=frozenset(_split(excluded_keywords)),
            preferred_scope_keywords=frozenset(_split(preferred_scope_keywords)),
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
    target_titles: str = Form(""),
    adjacent_titles: str = Form(""),
    excluded_titles: str = Form(""),
    target_industries: str = Form(""),
    adjacent_industries: str = Form(""),
    must_have_keywords: str = Form(""),
    strong_keywords: str = Form(""),
    nice_to_have_keywords: str = Form(""),
    excluded_keywords: str = Form(""),
    preferred_scope_keywords: str = Form(""),
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
            target_titles=frozenset(_split(target_titles)),
            adjacent_titles=frozenset(_split(adjacent_titles)),
            excluded_titles=frozenset(_split(excluded_titles)),
            target_industries=frozenset(_split(target_industries)),
            adjacent_industries=frozenset(_split(adjacent_industries)),
            must_have_keywords=frozenset(_split(must_have_keywords)),
            strong_keywords=frozenset(_split(strong_keywords)),
            nice_to_have_keywords=frozenset(_split(nice_to_have_keywords)),
            excluded_keywords=frozenset(_split(excluded_keywords)),
            preferred_scope_keywords=frozenset(_split(preferred_scope_keywords)),
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
            pass  # redirect anyway; error shown via status
    return RedirectResponse("/dashboard/profiles", status_code=303)


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
