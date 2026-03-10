"""Integration tests for the FastAPI endpoints."""

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a TestClient for the Exec Radar API."""
    return TestClient(create_app())


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self, client: TestClient) -> None:
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "version" in data


class TestJobsEndpoint:
    def test_list_jobs_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200

    def test_list_jobs_response_shape(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs")
        data = response.json()
        assert "total" in data
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_list_jobs_contains_demo_data(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs")
        data = response.json()
        assert data["total"] >= 2

    def test_get_existing_job(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs/demo-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "demo-001"
        assert data["title"] == "Chief Technology Officer"

    def test_get_nonexistent_job_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs/does-not-exist")
        assert response.status_code == 404

    def test_get_job_score(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs/demo-001/score")
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["job_id"] == "demo-001"

    def test_list_jobs_pagination(self, client: TestClient) -> None:
        response = client.get("/api/v1/jobs?limit=1&skip=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) <= 1

    def test_ingest_job(self, client: TestClient) -> None:
        payload = {
            "raw": {
                "source": "test",
                "source_id": "test-api-001",
                "url": "https://example.com/jobs/api-test",
                "title": "VP of Engineering",
                "company": "TestCo",
                "location": "Remote",
                "description": "Lead engineering teams with python and aws.",
                "salary_raw": "$200,000 - $240,000",
            }
        }
        response = client.post("/api/v1/jobs/ingest", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "VP of Engineering"
        assert data["id"] is not None
