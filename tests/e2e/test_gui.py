"""End-to-end GUI tests using Playwright.

These tests start the FastAPI application in a subprocess and verify
the dashboard renders correctly through a real Chromium browser.

Run with::

    pytest tests/e2e/ -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from apps.api.main import app

# ===================================================================
# Tests — Dashboard loads
# ===================================================================


class TestDashboardLoads:
    """Verify the dashboard page renders and displays core elements."""

    def test_page_loads_successfully(self, page: Page, base_url: str) -> None:
        response = page.goto(f"{base_url}/dashboard/")
        assert response is not None
        assert response.status == 200
        expect(page.locator("nav.navbar")).to_be_visible()

    def test_title_contains_exec_radar(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page).to_have_title("Dashboard \u2013 Exec Radar")

    def test_health_status_shown(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        status = page.locator("[data-testid='health-status']")
        expect(status).to_be_visible()
        expect(status).to_contain_text("Backend healthy")

    def test_health_version_shown(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        status = page.locator("[data-testid='health-status']")
        expect(status).to_contain_text("v0.1.0")

    def test_health_dot_is_green(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        dot = page.locator("[data-testid='health-status'] .status-dot")
        expect(dot).to_have_class("status-dot ok")


# ===================================================================
# Tests — Jobs table (with MockCollector data)
# ===================================================================


class TestJobsTable:
    """Verify jobs are displayed from the backend."""

    def test_jobs_card_visible(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        card = page.locator("[data-testid='jobs-card']")
        expect(card).to_be_visible()

    def test_jobs_table_rendered(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        table = page.locator("[data-testid='jobs-table']")
        expect(table).to_be_visible()

    def test_jobs_have_rows(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        rows = page.locator("[data-testid='job-row']")
        expect(rows.first).to_be_visible()
        assert rows.count() >= 1

    def test_job_count_matches_rows(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        rows = page.locator("[data-testid='job-row']")
        count = rows.count()
        header = page.locator("[data-testid='jobs-card'] .card-header h2")
        expect(header).to_contain_text(f"({count})")

    def test_table_columns_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        for col in ["Title", "Company", "Location", "Remote", "Seniority", "Score", "Source"]:
            expect(page.locator(f"[data-testid='jobs-table'] th:text-is('{col}')")).to_be_visible()

    def test_jobs_sorted_by_score_descending(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        scores = page.locator("[data-testid='job-row'] .score-value").all_text_contents()
        numeric_scores = [int(s.replace("%", "")) for s in scores]
        assert numeric_scores == sorted(numeric_scores, reverse=True)

    def test_score_bars_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        rows = page.locator("[data-testid='job-row']")
        for i in range(rows.count()):
            row = rows.nth(i)
            expect(row.locator(".score-bar")).to_be_visible()

    def test_source_column_shows_mock(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        first_row = page.locator("[data-testid='job-row']").first
        expect(first_row).to_contain_text("mock")

    def test_refresh_button_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        btn = page.locator("[data-testid='jobs-card'] .btn")
        expect(btn).to_be_visible()
        expect(btn).to_contain_text("Refresh")


# ===================================================================
# Tests — Empty state (TestClient, in-process, sync)
# ===================================================================


class TestEmptyState:
    """Verify the empty state when no jobs are returned."""

    def test_empty_state_shown(self) -> None:
        with patch(
            "apps.dashboard.app.run_pipeline",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with TestClient(app) as client:
                resp = client.get("/dashboard/")
                assert resp.status_code == 200
                assert 'data-testid="jobs-empty"' in resp.text
                assert "No opportunities found" in resp.text

    def test_empty_state_hides_table(self) -> None:
        with patch(
            "apps.dashboard.app.run_pipeline",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with TestClient(app) as client:
                resp = client.get("/dashboard/")
                assert 'data-testid="jobs-table"' not in resp.text


# ===================================================================
# Tests — Error state (TestClient, in-process, sync)
# ===================================================================


class TestErrorState:
    """Verify the error state when the pipeline fails."""

    def test_error_state_shown(self) -> None:
        with patch(
            "apps.dashboard.app.run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("collector timeout"),
        ):
            with TestClient(app) as client:
                resp = client.get("/dashboard/")
                assert resp.status_code == 200
                assert 'data-testid="jobs-error"' in resp.text
                assert "collector timeout" in resp.text

    def test_error_state_hides_table(self) -> None:
        with patch(
            "apps.dashboard.app.run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            with TestClient(app) as client:
                resp = client.get("/dashboard/")
                assert 'data-testid="jobs-table"' not in resp.text
