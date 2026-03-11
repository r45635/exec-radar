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
        expect(page.locator("[data-testid='navbar']")).to_be_visible()

    def test_title_contains_exec_radar(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page).to_have_title("Dashboard - Exec Radar")

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
# Tests — Toolbar (search + filters)
# ===================================================================


class TestToolbar:
    """Verify the toolbar is present with search and filter controls."""

    def test_toolbar_visible(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page.locator("[data-testid='toolbar']")).to_be_visible()

    def test_search_input_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page.locator("[data-testid='search-input']")).to_be_visible()

    def test_filter_dropdowns_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page.locator("[data-testid='filter-seniority']")).to_be_visible()
        expect(page.locator("[data-testid='filter-remote']")).to_be_visible()
        expect(page.locator("[data-testid='filter-status']")).to_be_visible()

    def test_refresh_button_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        btn = page.locator("[data-testid='btn-refresh']")
        expect(btn).to_be_visible()
        expect(btn).to_contain_text("Refresh")

    def test_view_toggle_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page.locator("[data-testid='view-table']")).to_be_visible()
        expect(page.locator("[data-testid='view-cards']")).to_be_visible()

    def test_pagination_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        expect(page.locator("[data-testid='pagination']")).to_be_visible()
        expect(page.locator("[data-testid='page-prev']")).to_be_visible()
        expect(page.locator("[data-testid='page-next']")).to_be_visible()

    def test_search_filters_rows(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        rows = page.locator("[data-testid='job-row']")
        total = rows.count()
        assert total >= 1
        page.fill("[data-testid='search-input']", "xyznonexistent999")
        page.wait_for_timeout(200)
        visible = page.locator("[data-testid='job-row']:not([hidden])").count()
        assert visible == 0
        page.fill("[data-testid='search-input']", "")
        page.wait_for_timeout(200)
        assert page.locator("[data-testid='job-row']:not([hidden])").count() == total


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
        badge = page.locator("[data-testid='job-count']")
        expect(badge).to_contain_text(f"({count})")

    def test_table_columns_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        for col in [
            "Title",
            "Company",
            "Location",
            "Remote",
            "Seniority",
            "Score",
            "Source",
            "Date",
        ]:
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

    def test_favorite_button_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        fav_btn = page.locator("[data-testid='btn-fav']").first
        expect(fav_btn).to_be_visible()

    def test_dismiss_button_present(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        dismiss_btn = page.locator("[data-testid='btn-dismiss']").first
        expect(dismiss_btn).to_be_visible()


# ===================================================================
# Tests — Detail panel
# ===================================================================


class TestDetailPanel:
    """Verify the slide-out detail panel works."""

    def test_detail_panel_hidden_initially(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        panel = page.locator("[data-testid='detail-panel']")
        expect(panel).not_to_have_class("detail-panel open")

    def test_clicking_row_opens_detail(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='job-title-btn']").first.click()
        panel = page.locator("[data-testid='detail-panel']")
        expect(panel).to_have_class("detail-panel open")

    def test_detail_shows_title(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        first_title = page.locator("[data-testid='job-title-btn']").first.text_content()
        page.locator("[data-testid='job-title-btn']").first.click()
        detail_title = page.locator("[data-testid='detail-title']")
        expect(detail_title).to_have_text(first_title or "")

    def test_detail_shows_score_breakdown(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='job-title-btn']").first.click()
        expect(page.locator("[data-testid='score-breakdown']")).to_be_visible()

    def test_detail_shows_meta(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='job-title-btn']").first.click()
        expect(page.locator("[data-testid='detail-meta']")).to_be_visible()

    def test_detail_shows_description(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='job-title-btn']").first.click()
        expect(page.locator("[data-testid='detail-description']")).to_be_visible()

    def test_close_button_closes_panel(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='job-title-btn']").first.click()
        panel = page.locator("[data-testid='detail-panel']")
        expect(panel).to_have_class("detail-panel open")
        page.locator("[data-testid='detail-close']").click()
        expect(panel).not_to_have_class("detail-panel open")

    def test_escape_closes_panel(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='job-title-btn']").first.click()
        panel = page.locator("[data-testid='detail-panel']")
        expect(panel).to_have_class("detail-panel open")
        page.keyboard.press("Escape")
        expect(panel).not_to_have_class("detail-panel open")

    def test_cards_view_renders(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.locator("[data-testid='view-cards']").click()
        cards_view = page.locator("[data-testid='cards-view']")
        expect(cards_view).to_be_visible()


# ===================================================================
# Tests — Favorites & Dismiss
# ===================================================================


class TestFavoritesAndDismiss:
    """Verify favorite and dismiss interactions."""

    def test_clicking_fav_toggles_class(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.evaluate("localStorage.clear()")
        page.reload()
        row = page.locator("[data-testid='job-row']").first
        fav_btn = row.locator("[data-testid='btn-fav']")
        expect(row).not_to_have_class("job-row favorited")
        fav_btn.click()
        expect(row).to_have_class("job-row favorited")
        fav_btn.click()
        expect(row).not_to_have_class("job-row favorited")

    def test_clicking_dismiss_toggles_class(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.evaluate("localStorage.clear()")
        page.reload()
        row = page.locator("[data-testid='job-row']").first
        dismiss_btn = row.locator("[data-testid='btn-dismiss']")
        expect(row).not_to_have_class("job-row dismissed")
        dismiss_btn.click()
        expect(row).to_have_class("job-row dismissed")

    def test_favorites_filter_shows_only_favorites(self, page: Page, base_url: str) -> None:
        page.goto(f"{base_url}/dashboard/")
        page.evaluate("localStorage.clear()")
        page.reload()
        page.select_option("[data-testid='filter-status']", "all")
        visible_rows = page.locator("[data-testid='job-row']:not([hidden])")
        expect(visible_rows.first).to_be_visible()
        visible_rows.first.locator("[data-testid='btn-fav']").click()
        page.select_option("[data-testid='filter-status']", "favorites")
        page.wait_for_timeout(200)
        visible = page.locator("[data-testid='job-row']:not([hidden])").count()
        assert visible >= 1


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
