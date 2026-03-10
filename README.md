# Exec Radar

AI-powered executive opportunity intelligence platform.

## Goal

Exec Radar continuously scans public sources for executive and senior operations opportunities, normalizes listings into a canonical schema, scores them against a target profile, and surfaces the most relevant roles through an API and dashboard.

## Initial scope

- Collect public job postings from selected sources
- Normalize postings into a shared schema
- Score opportunities against an executive profile
- Provide a ranked API output
- Prepare for future dashboard and notification workflows

## Planned stack

- Python 3.12+
- FastAPI
- Pydantic v2
- PostgreSQL
- pytest
- Ruff
- Docker

## Repository structure

- `apps/api`: API service
- `apps/worker`: scheduled and background jobs
- `apps/dashboard`: UI placeholder
- `packages/schemas`: shared models
- `packages/collectors`: source collectors
- `packages/normalizers`: canonical transformation logic
- `packages/rankers`: job-fit scoring logic
- `packages/notifications`: delivery and notification interfaces
- `tests`: unit and integration tests
- `docs`: architecture and roadmap

## Design principles

- Keep raw ingestion, normalization, and scoring separate
- Favor typed, modular, production-oriented code
- Avoid hardcoded secrets and personal profile data
- Prefer extensibility over early complexity

## Next steps

- Add canonical schemas
- Add sample collectors
- Add normalization pipeline
- Add scoring engine
- Add persistence and dashboard
