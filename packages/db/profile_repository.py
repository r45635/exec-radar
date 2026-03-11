"""Repository functions for profile management.

All functions accept an ``AsyncSession`` that the caller is responsible
for committing / rolling back.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import ProfileRecord
from packages.schemas.target_profile import TargetProfile


def _slugify(name: str) -> str:
    """Convert a profile name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


def _profile_to_json(profile: TargetProfile) -> str:
    """Serialize a TargetProfile to a JSON string for storage."""
    data = json.loads(profile.model_dump_json())
    # Convert frozensets to sorted lists for clean JSON
    for key, value in data.items():
        if isinstance(value, list):
            data[key] = sorted(value) if value else value
    return json.dumps(data, indent=2)


def _json_to_profile(json_str: str) -> TargetProfile:
    """Deserialize a JSON string to a TargetProfile."""
    data = json.loads(json_str)
    return TargetProfile(**data)


def _record_to_dict(record: ProfileRecord) -> dict:
    """Convert a ProfileRecord to a serializable dict."""
    return {
        "id": record.id,
        "name": record.name,
        "slug": record.slug,
        "description": record.description,
        "is_active": record.is_active,
        "is_suspended": record.is_suspended,
        "source_type": record.source_type,
        "profile_data": json.loads(record.profile_data_json),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_profile(
    session: AsyncSession,
    *,
    name: str,
    description: str = "",
    source_type: str = "ui",
    profile_data: TargetProfile | None = None,
    is_active: bool = False,
) -> ProfileRecord:
    """Create a new profile.

    If *is_active* is True, all other profiles are deactivated first.
    """
    slug = _slugify(name)

    # Check slug uniqueness
    stmt = select(ProfileRecord).where(ProfileRecord.slug == slug)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        msg = f"A profile with slug '{slug}' already exists."
        raise ValueError(msg)

    if is_active:
        await _deactivate_all(session)

    profile_json = _profile_to_json(profile_data or TargetProfile())

    record = ProfileRecord(
        name=name,
        slug=slug,
        description=description,
        source_type=source_type,
        profile_data_json=profile_json,
        is_active=is_active,
        is_suspended=False,
    )
    session.add(record)
    await session.flush()
    return record


async def update_profile(
    session: AsyncSession,
    profile_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    profile_data: TargetProfile | None = None,
) -> ProfileRecord | None:
    """Update an existing profile's mutable fields.

    Returns the updated record, or None if not found.
    """
    record = await get_profile_by_id(session, profile_id)
    if record is None:
        return None

    if name is not None:
        record.name = name
        record.slug = _slugify(name)
    if description is not None:
        record.description = description
    if profile_data is not None:
        record.profile_data_json = _profile_to_json(profile_data)

    record.updated_at = datetime.now(UTC)
    session.add(record)
    await session.flush()
    return record


async def list_profiles(session: AsyncSession) -> list[ProfileRecord]:
    """Return all profiles ordered by name."""
    stmt = select(ProfileRecord).order_by(ProfileRecord.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_profile_by_id(
    session: AsyncSession, profile_id: str
) -> ProfileRecord | None:
    """Return a single profile by ID, or None."""
    stmt = select(ProfileRecord).where(ProfileRecord.id == profile_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_profile(session: AsyncSession) -> ProfileRecord | None:
    """Return the currently active profile, or None."""
    stmt = select(ProfileRecord).where(
        ProfileRecord.is_active.is_(True),
        ProfileRecord.is_suspended.is_(False),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_profile(
    session: AsyncSession, profile_id: str
) -> bool:
    """Delete a profile. Returns True if deleted, False if not found."""
    record = await get_profile_by_id(session, profile_id)
    if record is None:
        return False
    await session.delete(record)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Activate / Suspend
# ---------------------------------------------------------------------------


async def _deactivate_all(session: AsyncSession) -> None:
    """Deactivate all profiles (helper for single-active rule)."""
    stmt = (
        update(ProfileRecord)
        .where(ProfileRecord.is_active.is_(True))
        .values(is_active=False, updated_at=datetime.now(UTC))
    )
    await session.execute(stmt)


async def activate_profile(
    session: AsyncSession, profile_id: str
) -> ProfileRecord | None:
    """Activate a profile. Deactivates all others first.

    Suspended profiles cannot be activated — unsuspend first.
    Returns the activated record or None if not found.
    """
    record = await get_profile_by_id(session, profile_id)
    if record is None:
        return None

    if record.is_suspended:
        msg = (
            f"Profile '{record.name}' is suspended. "
            "Unsuspend it before activating."
        )
        raise ValueError(msg)

    await _deactivate_all(session)
    record.is_active = True
    record.updated_at = datetime.now(UTC)
    session.add(record)
    await session.flush()
    return record


async def suspend_profile(
    session: AsyncSession, profile_id: str
) -> ProfileRecord | None:
    """Suspend a profile. If it was active, deactivates it too.

    Returns the suspended record or None if not found.
    """
    record = await get_profile_by_id(session, profile_id)
    if record is None:
        return None

    record.is_suspended = True
    record.is_active = False
    record.updated_at = datetime.now(UTC)
    session.add(record)
    await session.flush()
    return record


async def unsuspend_profile(
    session: AsyncSession, profile_id: str
) -> ProfileRecord | None:
    """Unsuspend a profile (does not auto-activate).

    Returns the unsuspended record or None if not found.
    """
    record = await get_profile_by_id(session, profile_id)
    if record is None:
        return None

    record.is_suspended = False
    record.updated_at = datetime.now(UTC)
    session.add(record)
    await session.flush()
    return record


# ---------------------------------------------------------------------------
# YAML import / export
# ---------------------------------------------------------------------------


def parse_yaml_to_profile(yaml_content: str) -> TargetProfile:
    """Parse YAML content into a validated TargetProfile.

    Raises:
        ValueError: If the YAML is malformed.
        ValidationError: If the data doesn't match the TargetProfile schema.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        msg = f"Invalid YAML: {exc}"
        raise ValueError(msg) from exc

    if data is None:
        return TargetProfile()

    if not isinstance(data, dict):
        msg = "YAML content must be a mapping (key: value), not a scalar or list."
        raise ValueError(msg)

    return TargetProfile(**data)


async def import_profile_from_yaml(
    session: AsyncSession,
    *,
    yaml_content: str,
    name: str,
    description: str = "",
    source_type: str = "file_import",
) -> ProfileRecord:
    """Parse YAML and create a new persisted profile.

    Raises ValueError or ValidationError on invalid input.
    """
    profile = parse_yaml_to_profile(yaml_content)
    return await create_profile(
        session,
        name=name,
        description=description,
        source_type=source_type,
        profile_data=profile,
    )


def export_profile_to_yaml(record: ProfileRecord) -> str:
    """Export a profile record to YAML string."""
    data = json.loads(record.profile_data_json)
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Active profile resolution (for pipeline integration)
# ---------------------------------------------------------------------------


async def resolve_active_target_profile(
    session: AsyncSession,
) -> TargetProfile:
    """Resolve the active TargetProfile from persistence.

    Falls back to the default TargetProfile if no active profile exists.
    """
    record = await get_active_profile(session)
    if record is None:
        return TargetProfile()
    return _json_to_profile(record.profile_data_json)
