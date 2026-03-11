"""API routes for profile management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError

from apps.api.profile_models import (
    ProfileActionResponse,
    ProfileCreateRequest,
    ProfileImportRequest,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from packages.db.models import ProfileRecord
from packages.db.profile_repository import (
    _record_to_dict,
    activate_profile,
    create_profile,
    delete_profile,
    export_profile_to_yaml,
    get_profile_by_id,
    import_profile_from_yaml,
    list_profiles,
    suspend_profile,
    unsuspend_profile,
    update_profile,
)
from packages.db.profile_session import get_session
from packages.schemas.target_profile import TargetProfile

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_response(record: ProfileRecord) -> ProfileResponse:
    return ProfileResponse(**_record_to_dict(record))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=ProfileListResponse)
async def api_list_profiles() -> ProfileListResponse:
    """List all profiles."""
    session = await get_session()
    async with session:
        records = await list_profiles(session)
        profiles = [_to_response(r) for r in records]
        return ProfileListResponse(count=len(profiles), profiles=profiles)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def api_get_profile(profile_id: str) -> ProfileResponse:
    """Get a single profile by ID."""
    session = await get_session()
    async with session:
        record = await get_profile_by_id(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return _to_response(record)


@router.post("", response_model=ProfileResponse, status_code=201)
async def api_create_profile(payload: ProfileCreateRequest) -> ProfileResponse:
    """Create a new profile."""
    session = await get_session()
    async with session:
        try:
            profile_data = None
            if payload.profile_data is not None:
                profile_data = TargetProfile(**payload.profile_data)

            record = await create_profile(
                session,
                name=payload.name,
                description=payload.description,
                source_type="ui",
                profile_data=profile_data,
                is_active=payload.is_active,
            )
            await session.commit()
            return _to_response(record)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid profile data: {exc}",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{profile_id}", response_model=ProfileResponse)
async def api_update_profile(
    profile_id: str, payload: ProfileUpdateRequest
) -> ProfileResponse:
    """Update an existing profile."""
    session = await get_session()
    async with session:
        try:
            profile_data = None
            if payload.profile_data is not None:
                profile_data = TargetProfile(**payload.profile_data)

            record = await update_profile(
                session,
                profile_id,
                name=payload.name,
                description=payload.description,
                profile_data=profile_data,
            )
            if record is None:
                raise HTTPException(status_code=404, detail="Profile not found")
            await session.commit()
            return _to_response(record)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid profile data: {exc}",
            ) from exc


@router.post("/{profile_id}/activate", response_model=ProfileActionResponse)
async def api_activate_profile(profile_id: str) -> ProfileActionResponse:
    """Activate a profile (deactivates all others)."""
    session = await get_session()
    async with session:
        try:
            record = await activate_profile(session, profile_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Profile not found")
            await session.commit()
            return ProfileActionResponse(
                message=f"Profile '{record.name}' is now active.",
                profile=_to_response(record),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{profile_id}/suspend", response_model=ProfileActionResponse)
async def api_suspend_profile(profile_id: str) -> ProfileActionResponse:
    """Suspend a profile."""
    session = await get_session()
    async with session:
        record = await suspend_profile(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        await session.commit()
        return ProfileActionResponse(
            message=f"Profile '{record.name}' has been suspended.",
            profile=_to_response(record),
        )


@router.post("/{profile_id}/unsuspend", response_model=ProfileActionResponse)
async def api_unsuspend_profile(profile_id: str) -> ProfileActionResponse:
    """Unsuspend a profile."""
    session = await get_session()
    async with session:
        record = await unsuspend_profile(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        await session.commit()
        return ProfileActionResponse(
            message=f"Profile '{record.name}' has been unsuspended.",
            profile=_to_response(record),
        )


@router.delete("/{profile_id}", status_code=204)
async def api_delete_profile(profile_id: str) -> None:
    """Delete a profile."""
    session = await get_session()
    async with session:
        deleted = await delete_profile(session, profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Profile not found")
        await session.commit()


@router.post("/import", response_model=ProfileResponse, status_code=201)
async def api_import_profile(payload: ProfileImportRequest) -> ProfileResponse:
    """Import a profile from inline YAML content."""
    session = await get_session()
    async with session:
        try:
            record = await import_profile_from_yaml(
                session,
                yaml_content=payload.yaml_content,
                name=payload.name,
                description=payload.description,
                source_type="file_import",
            )
            await session.commit()
            return _to_response(record)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"YAML import failed: {exc}",
            ) from exc


@router.post("/upload", response_model=ProfileResponse, status_code=201)
async def api_upload_profile(file: UploadFile, name: str = "") -> ProfileResponse:
    """Upload a YAML profile file through the browser."""
    if file.content_type and file.content_type not in (
        "application/x-yaml",
        "text/yaml",
        "text/x-yaml",
        "application/octet-stream",
        "text/plain",
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Upload a YAML file.",
        )

    content = await file.read()
    yaml_content = content.decode("utf-8")

    profile_name = name or (file.filename or "Uploaded Profile").removesuffix(
        ".yaml"
    ).removesuffix(".yml")

    session = await get_session()
    async with session:
        try:
            record = await import_profile_from_yaml(
                session,
                yaml_content=yaml_content,
                name=profile_name,
                description=f"Uploaded from {file.filename or 'file'}",
                source_type="upload",
            )
            await session.commit()
            return _to_response(record)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"YAML upload failed: {exc}",
            ) from exc


@router.get("/{profile_id}/export")
async def api_export_profile(profile_id: str) -> Response:
    """Export a profile as a downloadable YAML file."""
    session = await get_session()
    async with session:
        record = await get_profile_by_id(session, profile_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Profile not found")

        yaml_content = export_profile_to_yaml(record)
        filename = f"{record.slug}.yaml"
        return Response(
            content=yaml_content,
            media_type="application/x-yaml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
