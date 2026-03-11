# Development Guide

This document covers setup, architecture, testing, and extending Exec Radar.

**For general usage**, see [README.md](README.md).

## Table of Contents

1. [Developer Setup](#developer-setup)
2. [Project Structure](#project-structure)
3. [Architecture](#architecture)
4. [Testing](#testing)
5. [Extending](#extending)
6. [Database](#database)
7. [Troubleshooting](#troubleshooting)

---

## Developer Setup

### Prerequisites

- Python 3.12+
- Git
- venv (built-in)

### Installation

```bash
git clone https://github.com/r45635/exec-radar.git
cd exec-radar

# Create and activate venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install Playwright (for GUI tests)
python -m playwright install chromium
```

### Verify Installation

```bash
# Run tests
pytest -v

# Run E2E tests
pytest tests/e2e/ -v

# Start API
uvicorn apps.api.main:app --reload
# Visit http://localhost:8000/dashboard/
```

---

## Project Structure

```
exec-radar/
├── apps/
│   ├── api/
│   │   ├── main.py              # FastAPI app, /health, /jobs endpoints
│   │   └── routes.py            # Route handlers
│   ├── worker/
│   │   └── main.py              # Pipeline runner (collect → normalize → rank)
│   └── dashboard/
│       ├── app.py               # Jinja2 dashboard sub-application
│       ├── preferences_store.py # SQLite preferences backend
│       ├── templates/
│       │   ├── base.html        # Layout template
│       │   └── index.html       # Dashboard UI
│       └── static/
│           ├── style.css        # Styling
│           └── app.js           # Frontend logic
│
├── packages/
│   ├── schemas/
│   │   ├── raw_job.py           # RawJobPosting (from collector)
│   │   ├── normalized_job.py    # NormalizedJobPosting (after normalizer)
│   │   ├── scored_job.py        # ScoredJobPosting (after ranker)
│   │   ├── fit_score.py         # Scoring breakdown
│   │   └── target_profile.py    # User's matching criteria
│   │
│   ├── collectors/
│   │   ├── base.py              # BaseCollector ABC
│   │   ├── mock_collector.py    # Sample data
│   │   ├── greenhouse_collector.py  # Greenhouse Boards API
│   │   ├── lever_collector.py       # Lever Postings API
│   │   ├── ashby_collector.py       # Ashby career pages (window.__appData)
│   │   └── composite_collector.py   # Parallel multi-board aggregator
│   │
│   ├── normalizers/
│   │   ├── base.py              # BaseNormalizer ABC
│   │   └── simple_normalizer.py # Default: HTML→text, enum parsing
│   │
│   ├── rankers/
│   │   ├── base.py              # BaseRanker ABC
│   │   └── rule_based_ranker.py # Score against TargetProfile
│   │
│   ├── db/
│   │   ├── engine.py            # SQLAlchemy async setup
│   │   ├── models.py            # ORM models (RawJob, NormalizedJob, ScoredJob)
│   │   ├── repository.py        # CRUD operations
│   │   └── base.py              # Declarative base
│   │
│   ├── pipeline.py              # run_pipeline(), run_pipeline_with_persistence()
│   ├── services.py              # Component factory (collectors, normalizers, rankers)
│   ├── profile_loader.py        # Load TargetProfile from YAML
│   └── version.py               # __version__
│
├── tests/
│   ├── test_*.py                # Unit tests (pytest)
│   ├── e2e/
│   │   ├── conftest.py          # E2E fixtures (Playwright)
│   │   └── test_gui.py          # Browser-based tests
│   └── fixtures/
│       └── *.yaml               # Test data
│
├── examples/
│   └── sample_profile.yaml      # Template for TargetProfile
│
├── migrations/
│   └── versions/                # Alembic schema migrations
│
├── docs/
│   ├── architecture.md          # System design details
│   └── roadmap.md               # Planned features
│
├── pyproject.toml               # Build, dependencies, tool config
├── pytest.ini                   # Pytest configuration
├── .env.example                 # Environment variable template
├── Dockerfile                   # Container image
└── alembic.ini                  # Database migration config
```

---

## Architecture

### Data Flow

```
User/API
   ↓
[Collector]  (e.g., GreenhouseCollector, LeverCollector, AshbyCollector)
   ↓ HTTP GET → ATS API / career page → RawJobPosting list
[Normalizer] (SimpleNormalizer)
   ↓ Parse HTML, extract seniority/location → NormalizedJobPosting list
[Ranker]     (RuleBasedRanker)
   ↓ Score against TargetProfile → ScoredJobPosting list
[Repository] (Optional persistence)
   ↓ INSERT/UPDATE to database
[API / Dashboard]
   ↓ Serve via /jobs endpoint or render HTML
User sees results
```

### Key Abstractions

**BaseCollector**
```python
class BaseCollector(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def collect(self) -> list[RawJobPosting]: ...
```

Implementations:
- `MockCollector` — 5 sample postings
- `GreenhouseCollector` — Real jobs from Greenhouse Boards API
- `LeverCollector` — Real jobs from Lever Postings API
- `AshbyCollector` — Real jobs from Ashby career pages
- `CompositeCollector` — Parallel aggregation of multiple collectors

**BaseNormalizer**
```python
class BaseNormalizer(ABC):
    @abstractmethod
    async def normalize(
        self, postings: list[RawJobPosting]
    ) -> list[NormalizedJobPosting]: ...
```

Implementations:
- `SimpleNormalizer` — HTML parsing, enum inference

**BaseRanker**
```python
class BaseRanker(ABC):
    @abstractmethod
    async def rank(
        self, postings: list[NormalizedJobPosting]
    ) -> list[ScoredJobPosting]: ...
```

Implementations:
- `RuleBasedRanker` — Rule-based scoring against TargetProfile

### Schemas (Pydantic v2)

All data is validated at stage boundaries.

**RawJobPosting** — As received from source
```python
RawJobPosting(
    source="greenhouse:discord",
    source_id="12345",
    source_url="https://...",
    title="VP of Operations",
    company=None,
    location="Remote",
    description="<html>...",
    salary_raw="$200k-$300k",
    posted_at=datetime(...),
    collected_at=datetime(...),
    meta={"departments": "Ops, Strategy"}
)
```

**NormalizedJobPosting** — Standardized format
```python
NormalizedJobPosting(
    id="<hash>",
    title="VP of Operations",
    company="Discord",
    location="Remote",
    seniority=Seniority.vp,
    remote_policy=RemotePolicy.remote,
    description_plain="Clear text",
    tags=["operations", "strategy"],
    salary_min=200000,
    salary_max=300000,
    salary_currency="USD",
    source="greenhouse:discord",
    source_id="12345",
    source_url="https://...",
    posted_at=datetime(...),
    normalized_at=datetime(...)
)
```

**ScoredJobPosting** — With rankings
```python
ScoredJobPosting(
    job=NormalizedJobPosting(...),
    score=FitScore(
        overall=0.85,
        title_match=0.9,
        seniority_match=1.0,
        location_match=0.7,
        skills_match=0.8,
        explanation="Title matches; seniority perfect; location acceptable"
    )
)
```

---

## Testing

### Unit Tests

Test framework: **pytest** + **pytest-asyncio**

```bash
# Run all unit tests
pytest -v

# Run specific test file
pytest tests/test_greenhouse_collector.py -v

# Run with coverage
pytest --cov=packages tests/

# Run tests matching pattern
pytest -k "greenhouse" -v
```

### E2E GUI Tests

Browser-based tests using **Playwright**.

```bash
# One-time setup
python -m playwright install chromium

# Run E2E tests
pytest tests/e2e/ -v

# Run specific E2E test
pytest tests/e2e/test_gui.py::test_dashboard_loads -v

# Headed mode (see browser)
pytest tests/e2e/ --headed
```

### Mocking HTTP in Tests

Example from `test_greenhouse_collector.py`:

```python
class _FakeTransport(httpx.AsyncBaseTransport):
    """Mock HTTP responses without network."""

    def __init__(self, json_data: dict) -> None:
        self._json_data = json_data

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = json.dumps(self._json_data).encode()
        return httpx.Response(200, content=body, request=request)

# Use in test
client = httpx.AsyncClient(transport=_FakeTransport({"jobs": [...]}))
collector = GreenhouseCollector(board_token="test", http_client=client)
```

### Test Structure

```
tests/
├── test_schemas.py          # Schema validation
├── test_collector.py        # Mock collector tests
├── test_greenhouse_collector.py  # Greenhouse API tests (mocked)
├── test_normalizers.py      # Normalization logic
├── test_rankers.py          # Scoring logic
├── test_pipeline.py         # Full pipeline integration
├── e2e/
│   ├── conftest.py          # Playwright fixtures
│   └── test_gui.py          # Browser tests
└── fixtures/
    └── profiles/            # Test YAML profiles
```

---

## Extending

### Adding a Collector

To fetch from a new job source:

1. **Create a new module** under `packages/collectors/`:

```python
# packages/collectors/linkedin_collector.py
from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

class LinkedInCollector(BaseCollector):
    """Fetches jobs from LinkedIn API."""

    def __init__(self, search_query: str) -> None:
        self._query = search_query

    @property
    def source_name(self) -> str:
        return f"linkedin:{self._query}"

    async def collect(self) -> list[RawJobPosting]:
        # Make HTTP request to LinkedIn API
        # Map response to RawJobPosting
        # Return list
        pass
```

2. **Add tests** in `tests/test_linkedin_collector.py` with mocked HTTP:

```python
async def test_fetch_jobs():
    client = httpx.AsyncClient(transport=_FakeTransport(...))
    collector = LinkedInCollector(search_query="VP Operations", http_client=client)
    jobs = await collector.collect()
    assert len(jobs) > 0
    assert jobs[0].source == "linkedin:VP Operations"
```

3. **Register in** `packages/services.py`:

```python
def build_collector(collector_name: str | None = None) -> BaseCollector:
    name = (collector_name or os.getenv("EXEC_RADAR_COLLECTOR", "mock")).lower()

    if name == "linkedin":
        query = os.getenv("EXEC_RADAR_LINKEDIN_SEARCH")
        if not query:
            raise ValueError("LinkedIn requires EXEC_RADAR_LINKEDIN_SEARCH")
        return LinkedInCollector(search_query=query)

    # ... existing cases
```

4. **Document in README.md** with examples and env vars.

### Adding a Normalizer

Transform raw postings to standard format. Extend `BaseNormalizer`:

```python
# packages/normalizers/advanced_normalizer.py
class AdvancedNormalizer(BaseNormalizer):
    """More sophisticated normalization with NLP."""

    async def normalize(self, postings: list[RawJobPosting]) -> list[NormalizedJobPosting]:
        # Use spaCy, transformers, etc.
        # Extract salary ranges more reliably
        # Infer seniority from job titles with ML
        pass
```

Register in `packages/services.py`:

```python
def build_normalizer(normalizer_name: str | None = None) -> BaseNormalizer:
    name = (normalizer_name or os.getenv("EXEC_RADAR_NORMALIZER", "simple")).lower()

    if name == "advanced":
        return AdvancedNormalizer()

    return SimpleNormalizer()
```

### Adding a Ranker

Change scoring logic. Extend `BaseRanker`:

```python
# packages/rankers/ml_ranker.py
class MLRanker(BaseRanker):
    """ML-based scoring."""

    def __init__(self, model_path: str) -> None:
        self._model = load_model(model_path)

    async def rank(self, postings: list[NormalizedJobPosting]) -> list[ScoredJobPosting]:
        # Use trained model for scoring
        pass
```

---

## Database

### Async Setup

Uses **SQLAlchemy 2.0** with async drivers:

```python
# packages/db/engine.py
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    echo=False
)
```

Supported databases:
- PostgreSQL (recommended) — `postgresql+asyncpg://`
- MySQL — `mysql+aiomysql://`
- SQLite (dev only) — Requires `aiosqlite` (not async by default)

### ORM Models

```python
# packages/db/models.py
class RawJobModel(Base):
    __tablename__ = "raw_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    source: Mapped[str]
    source_id: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)  # Full RawJobPosting
    collected_at: Mapped[datetime]

class NormalizedJobModel(Base):
    __tablename__ = "normalized_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    data: Mapped[dict]  # Full NormalizedJobPosting

class ScoredJobModel(Base):
    __tablename__ = "scored_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    data: Mapped[dict]  # Full ScoredJobPosting
```

### Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add scored_jobs table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Persistence Pipeline

```python
# packages/pipeline.py
async def run_pipeline_with_persistence(
    collector: BaseCollector,
    normalizer: BaseNormalizer,
    ranker: BaseRanker,
    session: AsyncSession,
) -> list[ScoredJobPosting]:
    # Collect
    raw = await collector.collect()
    repo.save_raw_jobs(raw, session)

    # Normalize
    normalized = await normalizer.normalize(raw)
    repo.save_normalized_jobs(normalized, session)

    # Rank
    scored = await ranker.rank(normalized)
    repo.save_scored_jobs(scored, session)

    return scored
```

---

## Troubleshooting

### "The asyncio extension requires an async driver"

**Problem:** Using SQLite with async engine.

**Solution:** Use PostgreSQL or MySQL, or remove `EXEC_RADAR_DATABASE_URL` to run in-memory.

### Tests hanging

**Problem:** Event loop conflicts in pytest-asyncio.

**Solution:** E2E tests run in separate session. See `tests/e2e/conftest.py`.

### Greenhouse API returning 403

**Problem:** Invalid board token or rate limiting.

**Solution:**
- Check board token exists (e.g., `curl https://boards-api.greenhouse.io/v1/boards/discord/jobs`)
- Wait a minute, then retry (rate limit)
- See [Greenhouse docs](https://developers.greenhouse.io/job-board.html)

### Dashboard not showing jobs

**Problem:** Collector returning empty list.

**Solutions:**
- Check `EXEC_RADAR_COLLECTOR` env var is set correctly
- Test collector directly: `python -c "from packages.collectors.greenhouse_collector import GreenhouseCollector; import asyncio; asyncio.run(GreenhouseCollector(board_token='discord').collect())"`
- Check logs for errors

### Migrations failing

**Problem:** Database schema mismatch.

**Solution:**
```bash
# Check current state
alembic current

# Upgrade to latest
alembic upgrade head

# Force downgrade if needed
alembic downgrade base
alembic upgrade head
```

---

## Code Style

### Linting

```bash
# Format and check
ruff check . --fix

# Strict type checking (mypy)
mypy packages/ --strict
```

### Standards

- Type hints on all public functions
- Docstrings on all public classes/functions
- No hardcoded values (use env vars or config)
- Async/await for I/O (HTTP, database)
- Pydantic models for all data boundaries

### Commit Messages

```
feat(collector): add LinkedIn collector
fix(normalizer): handle missing seniority field
docs: update DEVELOPMENT guide
test(greenhouse): add edge case for empty response
refactor(db): simplify repository queries
```

---

## Contributing

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Make changes + tests
4. Run full suite (`pytest -v && pytest tests/e2e/ -v`)
5. Open a PR

---

## Resources

- [Architecture Deep Dive](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic v2](https://docs.pydantic.dev)
- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)
