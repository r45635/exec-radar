"""Tests for the FastAPI endpoints."""

from __future__ import annotations

from httpx import AsyncClient

from packages.version import __version__


class TestHealthEndpoint:
    """Tests for GET /health."""

    async def test_returns_200(self, client: AsyncClient) -> None:
        """Health endpoint should return 200."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_response_body(self, client: AsyncClient) -> None:
        """Health response should contain status and version."""
        resp = await client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == __version__


class TestJobsEndpoint:
    """Tests for GET /jobs."""

    async def test_returns_200(self, client: AsyncClient) -> None:
        """Jobs endpoint should return 200."""
        resp = await client.get("/jobs")
        assert resp.status_code == 200

    async def test_response_structure(self, client: AsyncClient) -> None:
        """Response should contain count and scored jobs."""
        resp = await client.get("/jobs")
        data = resp.json()
        assert "count" in data
        assert "jobs" in data
        assert data["count"] > 0

    async def test_jobs_sorted_by_score(self, client: AsyncClient) -> None:
        """Jobs should be sorted by overall score, descending."""
        resp = await client.get("/jobs")
        jobs = resp.json()["jobs"]
        scores = [j["score"]["overall"] for j in jobs]
        assert scores == sorted(scores, reverse=True)

    async def test_each_job_has_score(self, client: AsyncClient) -> None:
        """Every returned job should have a corresponding score."""
        resp = await client.get("/jobs")
        for entry in resp.json()["jobs"]:
            assert "job" in entry
            assert "score" in entry
            assert entry["score"]["job_id"] == entry["job"]["id"]
