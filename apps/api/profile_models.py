"""Pydantic request/response models for the profile management API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileCreateRequest(BaseModel):
    """Payload for creating a new profile."""

    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    profile_data: dict | None = Field(
        default=None,
        description="TargetProfile data as a dict. Omit for defaults.",
    )
    is_active: bool = Field(default=False)


class ProfileUpdateRequest(BaseModel):
    """Payload for updating an existing profile."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=2000)
    profile_data: dict | None = Field(
        default=None,
        description="TargetProfile data as a dict.",
    )


class ProfileImportRequest(BaseModel):
    """Payload for importing a profile from YAML string."""

    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    yaml_content: str = Field(
        ..., min_length=1,
        description="Raw YAML content representing a TargetProfile.",
    )


class ProfileResponse(BaseModel):
    """A single profile in API responses."""

    id: str
    name: str
    slug: str
    description: str
    is_active: bool
    is_suspended: bool
    source_type: str
    profile_data: dict
    created_at: str | None
    updated_at: str | None


class ProfileListResponse(BaseModel):
    """Response for listing all profiles."""

    count: int
    profiles: list[ProfileResponse]


class ProfileActionResponse(BaseModel):
    """Generic response after a profile action (activate/suspend)."""

    message: str
    profile: ProfileResponse
