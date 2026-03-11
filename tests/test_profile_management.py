"""Tests for profile management — repository, API, YAML import/export."""

from __future__ import annotations

import json

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.main import app
from packages.db.base import Base
from packages.db.profile_repository import (
    activate_profile,
    create_profile,
    delete_profile,
    export_profile_to_yaml,
    get_active_profile,
    get_profile_by_id,
    import_profile_from_yaml,
    list_profiles,
    parse_yaml_to_profile,
    resolve_active_target_profile,
    suspend_profile,
    unsuspend_profile,
    update_profile,
)
from packages.db.profile_session import restore_real_database, use_test_database
from packages.schemas.target_profile import TargetProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session():
    """Create an in-memory SQLite async session for each test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
async def api_client():
    """Yield an async HTTP test client bound to the FastAPI app.

    Uses an in-memory database so the real profiles DB is never touched.
    """
    await use_test_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await restore_real_database()


# ---------------------------------------------------------------------------
# Repository — CRUD
# ---------------------------------------------------------------------------


class TestCreateProfile:
    """Tests for create_profile()."""

    async def test_creates_with_defaults(self, db_session: AsyncSession) -> None:
        record = await create_profile(db_session, name="Test Profile")
        assert record.name == "Test Profile"
        assert record.slug == "test-profile"
        assert record.is_active is False
        assert record.is_suspended is False
        assert record.source_type == "ui"
        assert json.loads(record.profile_data_json)

    async def test_creates_with_custom_data(self, db_session: AsyncSession) -> None:
        profile = TargetProfile(
            target_titles=frozenset({"cto", "vp engineering"}),
            weight_title=0.40,
        )
        record = await create_profile(
            db_session,
            name="Tech Profile",
            description="For tech roles",
            profile_data=profile,
        )
        data = json.loads(record.profile_data_json)
        assert "cto" in data["target_titles"]
        assert data["weight_title"] == 0.40

    async def test_duplicate_slug_raises(self, db_session: AsyncSession) -> None:
        await create_profile(db_session, name="My Profile")
        with pytest.raises(ValueError, match="already exists"):
            await create_profile(db_session, name="My Profile")

    async def test_create_active_deactivates_others(
        self, db_session: AsyncSession
    ) -> None:
        r1 = await create_profile(db_session, name="P1", is_active=True)
        r2 = await create_profile(db_session, name="P2", is_active=True)
        await db_session.refresh(r1)
        assert r1.is_active is False
        assert r2.is_active is True


class TestUpdateProfile:
    """Tests for update_profile()."""

    async def test_updates_name_and_description(
        self, db_session: AsyncSession
    ) -> None:
        record = await create_profile(db_session, name="Old Name")
        updated = await update_profile(
            db_session, record.id, name="New Name", description="Updated"
        )
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.slug == "new-name"
        assert updated.description == "Updated"

    async def test_updates_profile_data(self, db_session: AsyncSession) -> None:
        record = await create_profile(db_session, name="P1")
        new_profile = TargetProfile(weight_title=0.50)
        updated = await update_profile(
            db_session, record.id, profile_data=new_profile
        )
        assert updated is not None
        data = json.loads(updated.profile_data_json)
        assert data["weight_title"] == 0.50

    async def test_not_found_returns_none(self, db_session: AsyncSession) -> None:
        result = await update_profile(db_session, "nonexistent", name="X")
        assert result is None


class TestListAndGetProfile:
    """Tests for list_profiles() and get_profile_by_id()."""

    async def test_list_empty(self, db_session: AsyncSession) -> None:
        records = await list_profiles(db_session)
        assert records == []

    async def test_list_returns_all(self, db_session: AsyncSession) -> None:
        await create_profile(db_session, name="A Profile")
        await create_profile(db_session, name="B Profile")
        records = await list_profiles(db_session)
        assert len(records) == 2
        assert records[0].name == "A Profile"  # sorted by name

    async def test_get_by_id(self, db_session: AsyncSession) -> None:
        record = await create_profile(db_session, name="Findme")
        found = await get_profile_by_id(db_session, record.id)
        assert found is not None
        assert found.name == "Findme"

    async def test_get_not_found(self, db_session: AsyncSession) -> None:
        found = await get_profile_by_id(db_session, "nope")
        assert found is None


class TestDeleteProfile:
    """Tests for delete_profile()."""

    async def test_delete_existing(self, db_session: AsyncSession) -> None:
        record = await create_profile(db_session, name="ToDelete")
        assert await delete_profile(db_session, record.id) is True
        assert await get_profile_by_id(db_session, record.id) is None

    async def test_delete_not_found(self, db_session: AsyncSession) -> None:
        assert await delete_profile(db_session, "nope") is False


# ---------------------------------------------------------------------------
# Repository — Activate / Suspend
# ---------------------------------------------------------------------------


class TestActivateProfile:
    """Tests for the single-active-profile rule."""

    async def test_activate_deactivates_others(
        self, db_session: AsyncSession
    ) -> None:
        r1 = await create_profile(db_session, name="P1", is_active=True)
        r2 = await create_profile(db_session, name="P2")
        await activate_profile(db_session, r2.id)
        await db_session.refresh(r1)
        assert r1.is_active is False
        assert r2.is_active is True

    async def test_activate_suspended_raises(
        self, db_session: AsyncSession
    ) -> None:
        record = await create_profile(db_session, name="Susp")
        await suspend_profile(db_session, record.id)
        with pytest.raises(ValueError, match="suspended"):
            await activate_profile(db_session, record.id)

    async def test_activate_not_found(self, db_session: AsyncSession) -> None:
        result = await activate_profile(db_session, "nope")
        assert result is None

    async def test_get_active_profile(self, db_session: AsyncSession) -> None:
        await create_profile(db_session, name="P1")
        r2 = await create_profile(db_session, name="P2", is_active=True)
        active = await get_active_profile(db_session)
        assert active is not None
        assert active.id == r2.id

    async def test_no_active_profile(self, db_session: AsyncSession) -> None:
        await create_profile(db_session, name="P1")
        active = await get_active_profile(db_session)
        assert active is None


class TestSuspendProfile:
    """Tests for suspend/unsuspend."""

    async def test_suspend_active_deactivates(
        self, db_session: AsyncSession
    ) -> None:
        record = await create_profile(db_session, name="P1", is_active=True)
        await suspend_profile(db_session, record.id)
        assert record.is_suspended is True
        assert record.is_active is False

    async def test_unsuspend(self, db_session: AsyncSession) -> None:
        record = await create_profile(db_session, name="P1")
        await suspend_profile(db_session, record.id)
        await unsuspend_profile(db_session, record.id)
        assert record.is_suspended is False
        # Not auto-activated
        assert record.is_active is False

    async def test_suspend_not_found(self, db_session: AsyncSession) -> None:
        assert await suspend_profile(db_session, "nope") is None

    async def test_unsuspend_not_found(self, db_session: AsyncSession) -> None:
        assert await unsuspend_profile(db_session, "nope") is None


# ---------------------------------------------------------------------------
# YAML import / export
# ---------------------------------------------------------------------------


class TestYamlImportExport:
    """Tests for YAML parsing, import, and export."""

    def test_parse_valid_yaml(self) -> None:
        yaml_str = "target_titles:\n  - coo\n  - cto\nweight_title: 0.4\n"
        profile = parse_yaml_to_profile(yaml_str)
        assert "coo" in profile.target_titles
        assert profile.weight_title == 0.4

    def test_parse_empty_yaml(self) -> None:
        profile = parse_yaml_to_profile("")
        assert profile == TargetProfile()

    def test_parse_invalid_yaml_syntax(self) -> None:
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_yaml_to_profile(":\n  - :\n  invalid: [\n")

    def test_parse_non_dict_yaml(self) -> None:
        with pytest.raises(ValueError, match="mapping"):
            parse_yaml_to_profile("- item1\n- item2\n")

    def test_parse_invalid_schema(self) -> None:
        with pytest.raises(ValidationError):
            parse_yaml_to_profile("weight_title: 5.0\n")  # > 1.0

    async def test_import_creates_profile(
        self, db_session: AsyncSession
    ) -> None:
        yaml_str = "target_titles:\n  - coo\nweight_title: 0.3\n"
        record = await import_profile_from_yaml(
            db_session,
            yaml_content=yaml_str,
            name="YAML Import",
            description="From YAML",
            source_type="file_import",
        )
        assert record.name == "YAML Import"
        assert record.source_type == "file_import"
        data = json.loads(record.profile_data_json)
        assert "coo" in data["target_titles"]

    async def test_export_produces_valid_yaml(
        self, db_session: AsyncSession
    ) -> None:
        profile = TargetProfile(
            target_titles=frozenset({"coo"}),
            weight_title=0.30,
        )
        record = await create_profile(
            db_session, name="Export Me", profile_data=profile
        )
        yaml_str = export_profile_to_yaml(record)
        parsed = yaml.safe_load(yaml_str)
        assert isinstance(parsed, dict)
        assert "coo" in parsed.get("target_titles", [])
        assert parsed["weight_title"] == 0.30

    async def test_roundtrip_yaml(self, db_session: AsyncSession) -> None:
        """Export → reimport should produce equivalent profile data."""
        original = TargetProfile(
            target_titles=frozenset({"vp operations", "coo"}),
            weight_industry=0.20,
        )
        record = await create_profile(
            db_session, name="Roundtrip", profile_data=original
        )
        exported = export_profile_to_yaml(record)
        reimported = parse_yaml_to_profile(exported)
        assert reimported.target_titles == original.target_titles
        assert reimported.weight_industry == original.weight_industry


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


class TestResolveActiveProfile:
    """Tests for resolve_active_target_profile()."""

    async def test_returns_default_when_none_active(
        self, db_session: AsyncSession
    ) -> None:
        profile = await resolve_active_target_profile(db_session)
        assert profile == TargetProfile()

    async def test_returns_active_profile(
        self, db_session: AsyncSession
    ) -> None:
        custom = TargetProfile(weight_title=0.50)
        await create_profile(
            db_session,
            name="Active",
            profile_data=custom,
            is_active=True,
        )
        resolved = await resolve_active_target_profile(db_session)
        assert resolved.weight_title == 0.50

    async def test_suspended_active_not_returned(
        self, db_session: AsyncSession
    ) -> None:
        record = await create_profile(
            db_session, name="Susp", is_active=True
        )
        await suspend_profile(db_session, record.id)
        resolved = await resolve_active_target_profile(db_session)
        assert resolved == TargetProfile()


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


class TestProfileAPI:
    """Integration tests for the profile REST API."""

    async def test_list_empty(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 0

    async def test_create_and_get(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles",
            json={"name": "API Test Profile", "description": "Created via API"},
        )
        assert resp.status_code == 201
        profile = resp.json()
        assert profile["name"] == "API Test Profile"
        assert profile["slug"] == "api-test-profile"

        # GET by id
        resp2 = await api_client.get(f"/profiles/{profile['id']}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "API Test Profile"

    async def test_create_with_profile_data(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post(
            "/profiles",
            json={
                "name": "Custom Data Profile",
                "profile_data": {
                    "target_titles": ["coo", "cto"],
                    "weight_title": 0.40,
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()["profile_data"]
        assert "coo" in data["target_titles"]
        assert data["weight_title"] == 0.40

    async def test_create_invalid_data(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles",
            json={
                "name": "Bad Profile",
                "profile_data": {"weight_title": 5.0},
            },
        )
        assert resp.status_code == 422

    async def test_update(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles", json={"name": "Update Me"}
        )
        pid = resp.json()["id"]
        resp2 = await api_client.put(
            f"/profiles/{pid}",
            json={"name": "Updated Name", "description": "New desc"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Updated Name"

    async def test_activate(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles", json={"name": "Activate Me"}
        )
        pid = resp.json()["id"]
        resp2 = await api_client.post(f"/profiles/{pid}/activate")
        assert resp2.status_code == 200
        assert resp2.json()["profile"]["is_active"] is True

    async def test_suspend(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles", json={"name": "Suspend Me"}
        )
        pid = resp.json()["id"]
        resp2 = await api_client.post(f"/profiles/{pid}/suspend")
        assert resp2.status_code == 200
        assert resp2.json()["profile"]["is_suspended"] is True

    async def test_activate_suspended_fails(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post(
            "/profiles", json={"name": "Susp Then Act"}
        )
        pid = resp.json()["id"]
        await api_client.post(f"/profiles/{pid}/suspend")
        resp3 = await api_client.post(f"/profiles/{pid}/activate")
        assert resp3.status_code == 400

    async def test_import_yaml(self, api_client: AsyncClient) -> None:
        yaml_content = "target_titles:\n  - coo\nweight_title: 0.3\n"
        resp = await api_client.post(
            "/profiles/import",
            json={
                "name": "Imported YAML",
                "yaml_content": yaml_content,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["source_type"] == "file_import"

    async def test_import_invalid_yaml(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles/import",
            json={
                "name": "Bad Import",
                "yaml_content": "weight_title: 5.0\n",
            },
        )
        assert resp.status_code == 422

    async def test_export_yaml(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles",
            json={
                "name": "Export Test",
                "profile_data": {"target_titles": ["coo"]},
            },
        )
        pid = resp.json()["id"]
        resp2 = await api_client.get(f"/profiles/{pid}/export")
        assert resp2.status_code == 200
        assert "coo" in resp2.text
        assert resp2.headers["content-type"] == "application/x-yaml"

    async def test_delete(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles", json={"name": "Delete Me"}
        )
        pid = resp.json()["id"]
        resp2 = await api_client.delete(f"/profiles/{pid}")
        assert resp2.status_code == 204
        resp3 = await api_client.get(f"/profiles/{pid}")
        assert resp3.status_code == 404

    async def test_get_not_found(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/profiles/nonexistent")
        assert resp.status_code == 404

    async def test_unsuspend(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/profiles", json={"name": "Unsuspend Me"}
        )
        pid = resp.json()["id"]
        await api_client.post(f"/profiles/{pid}/suspend")
        resp3 = await api_client.post(f"/profiles/{pid}/unsuspend")
        assert resp3.status_code == 200
        assert resp3.json()["profile"]["is_suspended"] is False

    async def test_single_active_rule_via_api(
        self, api_client: AsyncClient
    ) -> None:
        """Only one profile should be active at a time via API."""
        r1 = await api_client.post(
            "/profiles", json={"name": "SingleActive1"}
        )
        r2 = await api_client.post(
            "/profiles", json={"name": "SingleActive2"}
        )
        pid1 = r1.json()["id"]
        pid2 = r2.json()["id"]

        await api_client.post(f"/profiles/{pid1}/activate")
        await api_client.post(f"/profiles/{pid2}/activate")

        resp1 = await api_client.get(f"/profiles/{pid1}")
        resp2 = await api_client.get(f"/profiles/{pid2}")
        assert resp1.json()["is_active"] is False
        assert resp2.json()["is_active"] is True


# ---------------------------------------------------------------------------
# Dashboard UI routes
# ---------------------------------------------------------------------------


class TestDashboardProfiles:
    """Tests for dashboard profile UI endpoints."""

    async def test_profiles_list_page(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/dashboard/profiles")
        assert resp.status_code == 200
        assert "Profiles" in resp.text

    async def test_new_profile_form(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/dashboard/profiles/new")
        assert resp.status_code == 200
        assert "Create New Profile" in resp.text

    async def test_upload_form(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/dashboard/profiles/upload/form")
        assert resp.status_code == 200
        assert "Upload" in resp.text

    async def test_create_via_form(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/dashboard/profiles/new",
            data={
                "name": "UI Created",
                "description": "From form",
                "target_titles": "coo\nvp operations",
                "adjacent_titles": "",
                "excluded_titles": "",
                "target_industries": "",
                "adjacent_industries": "",
                "must_have_keywords": "",
                "strong_keywords": "",
                "nice_to_have_keywords": "",
                "excluded_keywords": "",
                "preferred_scope_keywords": "",
                "target_geographies": "",
                "weight_title": "0.25",
                "weight_seniority": "0.15",
                "weight_industry": "0.15",
                "weight_scope": "0.10",
                "weight_geography": "0.10",
                "weight_keyword_clusters": "0.25",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/dashboard/profiles" in resp.headers.get("location", "")
