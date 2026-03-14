# Architecture

## Overview

Exec Radar is an AI-powered executive job intelligence platform.  It continuously collects public job postings, normalizes them into a canonical schema, scores them against a target executive profile, and exposes results through an API.

## High-Level Data Flow

```
┌─────────────┐     ┌────────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────┐
│  Collectors  │────▶│  Pre-Filter │────▶│  Normalizers  │────▶│  Rankers   │────▶│   API    │
│  (raw data)  │     │  (title rx) │     │  (canonical)  │     │ (scored)  │     │ (serve)  │
└─────────────┘     └────────────┘     └──────────────┘     └───────────┘     └──────────┘
        │                                    │                  │
        └────────────────────────────────────┴──────────────────┘
                     ▼ (optional)
              ┌──────────────┐
              │  PostgreSQL   │
              │  persistence  │
              └──────────────┘
```

### Pipeline stages

| Stage       | Input              | Output                 | Location                     |
|-------------|--------------------|------------------------|------------------------------|
| Collect     | External source    | `RawJobPosting`        | `packages/collectors/`       |
| Pre-Filter  | `RawJobPosting`    | `RawJobPosting` (exec-only) | `packages/filters/`     |
| Normalize   | `RawJobPosting`    | `NormalizedJobPosting`  | `packages/normalizers/`      |
| Rank        | `NormalizedJobPosting` + `TargetProfile` | `FitScore` | `packages/rankers/`  |
| Serve       | Scored postings    | JSON API response      | `apps/api/`                  |
| Notify      | Scored postings    | Email / Slack / webhook | `packages/notifications/`   |

### Target Profile

The ranking engine scores jobs against a **configurable `TargetProfile`** rather than relying on hardcoded assumptions.  A profile describes:

- **target\_titles / adjacent\_titles / excluded\_titles** — desired, adjacent, and blacklisted job titles.
- **target\_seniority / acceptable\_seniority** — ideal vs. acceptable seniority.
- **preferred\_remote\_policies / target\_locations / target\_geographies** — remote-work and geographic preferences.
- **target\_industries / adjacent\_industries** — primary and adjacent industry preferences.
- **preferred\_companies / excluded\_companies** — company-level boost or penalty.
- **must\_have\_keywords** — deal-breaker keywords (penalized if ALL absent).
- **strong\_keywords** — high-value domain keywords.
- **nice\_to\_have\_keywords** — bonus uplift keywords.
- **excluded\_keywords** — anti-keywords that penalize a posting.
- **preferred\_scope\_keywords** — scope indicators (global, multi-site, P&L size).
- **weight\_\*** — per-dimension scoring weights across six dimensions.

#### Scoring dimensions (6)

| Dimension          | What it measures |
|--------------------|-----------------|
| **title**          | Target / adjacent / family-based title match |
| **seniority**      | C-level / VP / Director alignment |
| **industry**       | Target and adjacent industry overlap |
| **scope**          | Executive scope indicators in description |
| **geography**      | Remote policy + location + region match |
| **keyword\_clusters** | Domain cluster overlap (semiconductor, automotive, exec-ops, supply chain) |

#### Title normalization

Similar executive titles are mapped to canonical **title families** (e.g., "COO", "VP\_OPERATIONS", "HEAD\_MANUFACTURING") via `packages/normalizers/title_families.py`.  This allows semantically equivalent titles to score consistently.

#### Keyword clusters

Four domain-specific keyword clusters are defined in `packages/rankers/keyword_clusters.py`:

1. **semiconductor\_manufacturing** — wafer, fab, yield, cleanroom, etc.
2. **fabless\_foundry\_osat** — fabless, foundry, OSAT, advanced packaging, supplier quality, etc.
3. **automotive\_quality** — IATF, APQP, FMEA, OEM, etc.
4. **executive\_operations\_leadership** — lean, six sigma, P&L, transformation, etc.
5. **supply\_chain\_industrialization** — NPI, S&OP, procurement, ramp-up, etc.

#### Structured output

Each `FitScore` now includes:
- `dimension_scores` — dict of all six dimension scores.
- `why_matched` — list of positive-match reasons.
- `why_penalized` — list of penalty reasons.
- `red_flags` — list of hard negatives.

A sample profile lives at `examples/sample_profile.yaml`.  All fields have sensible defaults so `TargetProfile()` works out of the box.

Profiles can be loaded from YAML via `packages.profile_loader.load_profile(path)`.

### Job Identity

`NormalizedJobPosting.id` is derived deterministically from `sha256(source:source_id)`.  This ensures the same posting always receives the same internal ID across pipeline runs, enabling future deduplication and change detection.

### Collectors

| Collector | Source | Config |
|-----------|--------|--------|
| `MockCollector` | Hard-coded samples | None |
| `GreenhouseCollector` | Greenhouse Boards API (two-phase: light listing → title filter → detail fetch) | `board_token` / `EXEC_RADAR_GREENHOUSE_BOARD` |
| `LeverCollector` | Lever Postings API (unauthenticated public JSON) | `company_slug` / `EXEC_RADAR_LEVER_COMPANY` |
| `AshbyCollector` | Ashby career pages (embedded `window.__appData` JSON) | `company_slug` / `EXEC_RADAR_ASHBY_COMPANY` |

The active collector is controlled by the `EXEC_RADAR_COLLECTOR` environment variable (`mock` by default). Supported values: `mock`, `greenhouse`, `lever`, `ashby`, `all`, or combinations like `greenhouse+lever+ashby`. All real collectors accept an injected `httpx.AsyncClient`, keeping the network boundary explicit and easy to mock in tests.

#### Two-Phase Greenhouse Collection

The `GreenhouseCollector` uses a bandwidth-optimized two-phase strategy:

1. **Phase 1 — Light listing**: Fetches all jobs from a board *without* `content=true`, returning only titles and metadata (no HTML descriptions).
2. **Phase 1b — Title filter**: Applies `is_executive_title()` from `packages/filters/` to eliminate non-executive titles immediately.
3. **Phase 2 — Detail fetch**: Fetches individual `/jobs/{id}` detail pages *only* for the filtered executive titles, with a concurrency semaphore (`asyncio.Semaphore(10)`).

This avoids downloading full HTML descriptions for hundreds of irrelevant jobs (engineers, interns, analysts), reducing payload size and latency significantly.

#### Executive Title Pre-Filter

`packages/filters/__init__.py` provides a fast regex-based screen applied in the pipeline *before* normalization:

- `_EXEC_TITLE_RE` — matches VP, Director, Head of, Chief, SVP, GM, President, Executive, Principal, Managing Director, etc.
- `_JUNIOR_REJECT_RE` — rejects intern, trainee, coordinator, operator, clerk, etc. (with exclusions for "Associate Director", "Assistant VP")
- `_MID_REJECT_RE` — rejects analyst, specialist, engineer, scientist, developer, etc.

Logic: exec prefix → keep; no exec prefix + junior/mid marker → reject; unknown → keep (fail-open).

### Background Auto-Refresh

The dashboard (`apps/dashboard/app.py`) runs the pipeline in a background `asyncio.Task`:

- **Startup**: Pipeline runs immediately, populating the cache before the first request.
- **Periodic**: Every `_CACHE_TTL` seconds (default 300s), the pipeline re-runs automatically.
- **Non-blocking**: The dashboard always serves from cache — never blocks on collection.
- **Profile change**: Switching profiles triggers an immediate background refresh while serving stale data.

### Service Assembly

Component construction is centralized in `packages/services.py`.  The API routes and worker import `build_pipeline_components()` rather than wiring concrete implementations inline.  This keeps the application layer thin and makes it easy to swap implementations (e.g. a real collector or an LLM-based ranker).

Collector selection is driven by the `EXEC_RADAR_COLLECTOR` env var (`mock`, `greenhouse`, `lever`, `ashby`, `all`, or `+`-separated combos). Adding a new source requires only implementing `BaseCollector` and registering it in `build_collector()`.

### Named Source Sets

`packages/source_sets.py` provides a registry of curated board collections (`SourceSet`) spanning Greenhouse, Lever, and Ashby.  Each profile can reference a `preferred_source_set`, which takes priority over individual board tokens when building the collector.

Built-in sets:
- `semiconductor_exec_core` — 8 Greenhouse + 2 Lever + 1 Ashby boards
- `photonics_mems_ops` — 3 Greenhouse + 2 Lever + 2 Ashby boards
- `broad_hardware_supply_chain` — 7 Greenhouse + 2 Lever + 1 Ashby boards

Source sets can also be selected via `EXEC_RADAR_SOURCE_SET`.

### Multi-Profile Comparison

The dashboard includes a `/dashboard/compare` endpoint that scores the same set of jobs against two different profiles and renders a side-by-side delta table, sorted by |Δ| (absolute score difference).  This enables fast, visual profile tuning without manual inspection.

### Database Persistence

`packages/db/` provides async PostgreSQL persistence via SQLAlchemy 2.x:

| Module | Purpose |
|--------|---------|
| `engine.py` | Async engine + session factory (module-level singletons) |
| `base.py` | Declarative `Base` + `TimestampMixin` (created_at / updated_at) |
| `models.py` | ORM models: `SourceRunRecord`, `RawJobPostingRecord`, `NormalizedJobPostingRecord`, `FitScoreRecord` |
| `repository.py` | Thin async functions for persisting and querying pipeline data |

Key constraints:
- `raw_job_postings` has `UNIQUE(source, source_id)` for deduplication.
- `normalized_job_postings` has `UNIQUE(job_id)` linking to the deterministic SHA-256 id.
- `fit_scores` has `UNIQUE(job_id)` for one-score-per-posting.
- Foreign keys: `raw → source_run`, `normalized → raw`, `fit_score → normalized`.

The pipeline offers two paths:
- `run_pipeline()` — pure in-memory (used by the API, tests).
- `run_pipeline_with_persistence()` — same logic + DB writes (used by the worker when `EXEC_RADAR_DATABASE_URL` is set).

Migrations are managed by Alembic (`alembic/`).

## Repository Layout

```
exec-radar/
├── apps/
│   ├── api/            # FastAPI service (routes, config, models)
│   ├── worker/         # Background pipeline runner
│   └── dashboard/      # Interactive dashboard with background auto-refresh
├── packages/
│   ├── schemas/        # Pydantic v2 models (RawJobPosting, NormalizedJobPosting, FitScore, TargetProfile)
│   ├── db/             # SQLAlchemy ORM models, engine, repository (persistence layer)
│   ├── collectors/     # Source-specific ingestion (BaseCollector → MockCollector, GreenhouseCollector, …)
│   ├── filters/        # Executive title pre-filter (regex-based, ~68% noise reduction)
│   ├── normalizers/    # Raw-to-canonical transformation (BaseNormalizer → SimpleNormalizer, …)
│   ├── rankers/        # Scoring logic (BaseRanker → RuleBasedRanker, …)
│   └── notifications/  # Delivery channels (BaseNotifier, …)
├── alembic/            # Database migrations (Alembic)
├── tests/              # Unit and integration tests
├── docs/               # Architecture and roadmap
├── pyproject.toml      # Build config, Ruff, pytest
├── Dockerfile          # API container image
└── .env.example        # Environment variable template
```

## Design Principles

1. **Separation of concerns** — raw ingestion, normalization, and ranking are independent layers with clean interfaces (abstract base classes).
2. **Schema-first** — every data handoff is typed via Pydantic v2 models with strict validation.
3. **Extensibility** — adding a new collector, normalizer, or ranker requires only implementing an ABC; existing code remains untouched.
4. **No hardcoded secrets** — all configuration is driven by environment variables via `pydantic-settings`.
5. **Test-ready** — pytest with async support, 100 % type-annotated public surface.

## Technology Choices

| Concern        | Choice                                | Rationale                                      |
|----------------|---------------------------------------|-------------------------------------------------|
| Language       | Python 3.12+                          | Type hints, performance, ecosystem              |
| API framework  | FastAPI                               | Async, auto-docs, Pydantic integration          |
| Schemas        | Pydantic v2                           | Validation, serialization, settings             |
| Database       | PostgreSQL + SQLAlchemy 2.x async     | Production-grade, async support                 |
| Migrations     | Alembic                               | De-facto standard for SQLAlchemy                |
| Linting        | Ruff                                  | Fast, all-in-one Python linter + formatter      |
| Testing        | pytest + pytest-asyncio + aiosqlite   | De-facto standard, async support, in-memory DB  |
| Container      | Docker (slim Python image)            | Reproducible deployments                        |

## Future Components (not yet implemented)

- **pgvector** — vector similarity search for semantic matching.
- **Scheduling** — APScheduler or Celery Beat driving the worker pipeline on a cron.
- **LLM ranker** — GPT/Claude-based scoring for nuanced profile matching.
- **Notification channels** — Email, Slack, and webhook delivery.
- **Additional collectors** — Teamtailor, LinkedIn (Playwright-based), Indeed.
