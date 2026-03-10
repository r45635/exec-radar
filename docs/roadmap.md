# Roadmap

## Phase 0 — Foundation (current) ✅

- [x] Monorepo structure with `apps/` and `packages/`
- [x] Pydantic v2 schemas: `RawJobPosting`, `NormalizedJobPosting`, `FitScore`
- [x] Collector abstraction + `MockCollector`
- [x] Normalizer abstraction + `SimpleNormalizer` (regex-based)
- [x] Ranker abstraction + `RuleBasedRanker` (deterministic scoring)
- [x] Configurable `TargetProfile` model with sample YAML profile
- [x] Profile-driven ranking (no hardcoded assumptions in the ranker)
- [x] Profile loader utility (YAML → validated Pydantic model)
- [x] Deterministic job identity (`sha256(source:source_id)`)
- [x] Service assembly factory (`packages/services.py`)
- [x] Location, industry, and company preferences in profile
- [x] FastAPI with `GET /health` and `GET /jobs`
- [x] Unit tests for schemas, normalizer, ranker, collector, API, profile loader, services
- [x] `pyproject.toml` with Ruff + pytest configuration
- [x] Dockerfile for the API
- [x] Documentation: architecture and roadmap

## Phase 1 — Persistence & Real Collectors

- [x] PostgreSQL integration (async via `asyncpg` / SQLAlchemy 2.x)
- [x] Alembic migrations — initial schema
- [x] ORM models: `SourceRunRecord`, `RawJobPostingRecord`, `NormalizedJobPostingRecord`, `FitScoreRecord`
- [x] Repository layer for persisting pipeline outputs
- [x] Persistence-aware pipeline path (`run_pipeline_with_persistence`)
- [x] Worker uses persistence when `EXEC_RADAR_DATABASE_URL` is set
- [x] In-memory SQLite tests for ORM and repository
- [x] Greenhouse collector (public Boards API, no auth required)
- [ ] Lever collector (public API)
- [ ] Ashby / Teamtailor collectors
- [ ] LinkedIn collector (Playwright-based, future)
- [ ] Deduplication logic across sources

## Phase 2 — Intelligent Ranking

- [ ] pgvector for embedding storage
- [ ] Embedding-based semantic ranker (OpenAI / Sentence Transformers)
- [ ] LLM-based profile-match evaluator (GPT-4 / Claude)
- [x] Configurable target-profile definition (YAML / DB) — basic `TargetProfile` Pydantic model shipped
- [ ] A/B comparison of rule-based vs. semantic ranking

## Phase 3 — Scheduling & Notifications

- [ ] APScheduler or Celery Beat integration in `apps/worker`
- [ ] Configurable collection schedules per source
- [ ] Email digest notifier
- [ ] Slack notifier
- [ ] Webhook notifier
- [ ] Score-threshold alerting

## Phase 4 — Dashboard & UX

- [ ] Streamlit or React dashboard (`apps/dashboard`)
- [ ] Job browsing with filters (seniority, location, score)
- [ ] Saved searches and watchlists
- [ ] Application tracking
- [ ] Profile editor for target criteria

## Phase 5 — Production Hardening

- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Docker Compose for full local stack
- [ ] Rate limiting and caching for collectors
- [ ] Structured logging (JSON, correlation IDs)
- [ ] Observability: Prometheus metrics, health probes
- [ ] Secret management (Vault or cloud KMS)
- [ ] RBAC / API-key authentication

## Phase 6 — Advanced Intelligence

- [ ] Industry / company research enrichment
- [ ] Salary benchmarking via market data
- [ ] Auto-generated application drafts
- [ ] Network / warm-introduction suggestions
- [ ] Trend analytics and market-heat dashboard
