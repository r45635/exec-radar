# Exec Radar

AI-powered executive opportunity intelligence platform.

## Goal

Exec Radar continuously scans public sources for executive and senior operations opportunities, normalizes listings into a canonical schema, scores them against a target profile, and surfaces the most relevant roles through an API and dashboard.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/r45635/exec-radar.git
cd exec-radar
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Run tests
pytest

# 3. Start the API + Dashboard
uvicorn apps.api.main:app --reload

# 4. Try the endpoints
curl http://localhost:8000/health
curl http://localhost:8000/jobs

# 5. Open the dashboard
open http://localhost:8000/dashboard/
```

### Docker

```bash
docker build -t exec-radar .
docker run -p 8000:8000 exec-radar
```

## Stack

| Concern   | Choice              |
|-----------|---------------------|
| Language  | Python 3.12+        |
| API       | FastAPI             |
| Dashboard | Jinja2 templates    |
| Schemas   | Pydantic v2         |
| Linting   | Ruff                |
| Testing   | pytest + pytest-asyncio |
| GUI Tests | Playwright          |
| Container | Docker              |

## Repository Structure

```
exec-radar/
├── apps/
│   ├── api/            # FastAPI service (GET /health, GET /jobs)
│   ├── worker/         # Background pipeline runner
│   └── dashboard/      # Jinja2 dashboard (mounted at /dashboard)
│       ├── app.py      # FastAPI sub-app
│       ├── templates/  # base.html, index.html
│       └── static/     # style.css
├── packages/
│   ├── schemas/        # RawJobPosting, NormalizedJobPosting, FitScore, TargetProfile
│   ├── db/             # SQLAlchemy ORM models, engine, repository
│   ├── collectors/     # BaseCollector → MockCollector, GreenhouseCollector
│   ├── normalizers/    # BaseNormalizer → SimpleNormalizer
│   ├── rankers/        # BaseRanker → RuleBasedRanker
│   └── notifications/  # BaseNotifier (stub)
├── examples/           # Sample target profiles
├── tests/              # Unit + E2E tests (Playwright)
├── docs/               # Architecture and roadmap
├── pyproject.toml      # Build config, Ruff, pytest
├── Dockerfile          # API container image
└── .env.example        # Environment variable template
```

## Pipeline

```
Collectors  →  Normalizers  →  Rankers  →  API / Notifications
(raw data)     (canonical)     (scored)    (serve / alert)
```

## Target Profile

The ranking engine scores every posting against a configurable **`TargetProfile`** instead of hardcoded assumptions.  Customize it to describe the role you are pursuing:

```yaml
# examples/sample_profile.yaml (excerpt)
target_titles:
  - chief operating officer
  - vp of operations

target_seniority: [c_level, svp, vp]

target_locations:
  - New York
  - London

preferred_companies:
  - Acme Corp

required_keywords:
  - operations
  - supply chain
  - strategy

weight_title: 0.35
weight_seniority: 0.25
weight_location: 0.15
weight_skills: 0.25
```

All fields have sensible defaults — `TargetProfile()` works out of the box.
Load a custom profile from YAML with `load_profile("path/to/profile.yaml")`.
See [examples/sample_profile.yaml](examples/sample_profile.yaml) for the full template.

## Design Principles

- Separate raw ingestion, normalization, and ranking layers
- Schema-first — every handoff is a validated Pydantic model
- Extensible — add a new collector/normalizer/ranker by implementing one ABC
- No hardcoded secrets — env vars via `pydantic-settings`
- Fully typed, docstrings on all public surfaces

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)

## Collectors

### Mock (default)

Returns five hard-coded sample executive postings. No configuration needed.

### Greenhouse

Fetches real job listings from any company that uses the [Greenhouse ATS](https://developers.greenhouse.io/job-board.html) via its public Boards API. No authentication required.

```bash
# Set env vars and run the worker
export EXEC_RADAR_COLLECTOR=greenhouse
export EXEC_RADAR_GREENHOUSE_BOARD=discord   # any valid board token
python -m apps.worker.main
```

With persistence:

```bash
export EXEC_RADAR_COLLECTOR=greenhouse
export EXEC_RADAR_GREENHOUSE_BOARD=discord
export EXEC_RADAR_DATABASE_URL=postgresql+asyncpg://localhost:5432/exec_radar
alembic upgrade head
python -m apps.worker.main
```

Greenhouse board tokens to try: `discord`, `cloudflare`, `figma`, `notion`, `stripe`.

## Dashboard

The dashboard is a server-rendered Jinja2 UI mounted at `/dashboard` on the main FastAPI app. It displays:

- **Health status** — green/red indicator from the backend
- **Jobs table** — ranked opportunities with title, company, location, remote policy, seniority, fit score, and source
- **Empty / error states** — handled gracefully

```bash
# Start the server (API + Dashboard)
uvicorn apps.api.main:app --reload

# Open the dashboard
open http://localhost:8000/dashboard/
```

### Dashboard structure

```
apps/dashboard/
├── app.py               # FastAPI sub-app (Jinja2 + static files)
├── templates/
│   ├── base.html        # Layout: nav bar, version, CSS link
│   └── index.html       # Dashboard: health badge + jobs table
└── static/
    └── style.css        # Minimal responsive CSS
```

### GUI tests

End-to-end tests use Playwright (Chromium) against a real test server.
They run in a separate session to avoid event-loop conflicts with pytest-asyncio:

```bash
# Install Playwright browsers (one-time)
python -m playwright install chromium

# Run unit tests (default — e2e excluded)
pytest -v

# Run GUI / e2e tests
pytest tests/e2e/ -v

# Run everything
pytest -v && pytest tests/e2e/ -v
```

## License

MIT
