# Exec Radar

> AI-powered executive job intelligence platform – continuously collects public job postings,
> normalises them into a canonical schema, scores them against a target executive profile,
> and exposes the results through a REST API and a basic dashboard.

---

## Quick start

### Prerequisites

- Python 3.12+
- [pip](https://pip.pypa.io/) or [uv](https://github.com/astral-sh/uv)

### 1. Clone and set up environment

```bash
git clone https://github.com/your-org/exec-radar.git
cd exec-radar

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install all packages

```bash
pip install -e packages/schemas
pip install -e packages/collectors
pip install -e packages/normalizers
pip install -e packages/rankers
pip install -e packages/notifications
pip install -e apps/api
pip install pytest pytest-asyncio httpx ruff
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Run the API

```bash
python apps/api/server.py
# or
uvicorn app.main:app --reload --app-dir apps/api
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

### 5. Run the worker (optional)

```bash
python apps/worker/worker.py
```

### 6. Run tests

```bash
pytest
```

### 7. Lint

```bash
ruff check .
ruff format --check .
```

---

## Architecture overview

```
[Sources] → Collectors → RawJobPosting
                              ↓
                         Normalizers → NormalizedJobPosting
                                              ↓
                                         Rankers → FitScore
                                                       ↓
                                               API / Dashboard
```

| Layer        | Package                    | Description                                  |
|:-------------|:---------------------------|:---------------------------------------------|
| Schemas      | `packages/schemas`         | Shared Pydantic v2 models                    |
| Collectors   | `packages/collectors`      | Source adapters (Mock, HTTP, …)              |
| Normalizers  | `packages/normalizers`     | Canonical normalization (regex → LLM)        |
| Rankers      | `packages/rankers`         | Fit scoring (rule-based → embeddings)        |
| Notifications| `packages/notifications`   | Dispatch channels (email, Slack, …)          |
| API          | `apps/api`                 | FastAPI REST service                         |
| Worker       | `apps/worker`              | Async pipeline runner                        |
| Dashboard    | `apps/dashboard`           | UI (placeholder, future milestone)           |

See [docs/architecture.md](docs/architecture.md) for the full design.

---

## API endpoints

| Method | Path                        | Description                |
|:-------|:----------------------------|:---------------------------|
| GET    | `/health`                   | Liveness probe             |
| GET    | `/api/v1/jobs`              | Paginated job list         |
| GET    | `/api/v1/jobs/{id}`         | Single job posting         |
| GET    | `/api/v1/jobs/{id}/score`   | Fit score for a job        |
| POST   | `/api/v1/jobs/ingest`       | Ingest a raw posting       |

---

## Docker

```bash
# Build and start the API
docker build -t exec-radar-api .
docker run -p 8000:8000 exec-radar-api

# Or use Compose
docker-compose up
```

---

## Next steps

See [docs/roadmap.md](docs/roadmap.md) for the full plan. The immediate priorities are:

1. **PostgreSQL persistence** – replace in-memory store with SQLAlchemy + Alembic
2. **Real collectors** – Playwright scraper, RSS collector
3. **Semantic ranker** – sentence-transformer embeddings + pgvector
4. **Dashboard** – Streamlit or Next.js UI
5. **Notifications** – email and Slack digests for high-scoring jobs

---

## Contributing

- Follow the coding guidelines in [`.github/copilot-instructions.md`](.github/copilot-instructions.md).
- Run `ruff check .` and `pytest` before opening a PR.
- Keep modules small, add docstrings to all public APIs, and never commit secrets.

