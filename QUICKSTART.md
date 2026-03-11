# Quick Reference

Common commands and workflows for Exec Radar.

## Installation

```bash
git clone https://github.com/r45635/exec-radar.git
cd exec-radar
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

## Running

### Development Dashboard (with hot reload)

```bash
source .venv/bin/activate
uvicorn apps.api.main:app --reload
# Open http://localhost:8000/dashboard/
```

### With Mock Data (default)

```bash
uvicorn apps.api.main:app --reload
```

### With Real Data (Greenhouse)

```bash
export EXEC_RADAR_COLLECTOR=greenhouse
export EXEC_RADAR_GREENHOUSE_BOARD=discord
uvicorn apps.api.main:app --reload
```

Other boards: `cloudflare`, `figma`, `notion`, `stripe`, `remote`

### With Custom Profile

```bash
export EXEC_RADAR_TARGET_PROFILE=examples/sample_profile.yaml
uvicorn apps.api.main:app --reload
```

Edit `examples/sample_profile.yaml` to customize:
- `target_titles` — Job titles to match
- `target_seniority` — `[c_level, svp, vp, director, head, other]`
- `target_locations` — Preferred locations
- `required_keywords` — Must-have skills
- Scoring weights

### Run Pipeline (one-time fetch)

```bash
python -m apps.worker.main
```

With Greenhouse:
```bash
export EXEC_RADAR_COLLECTOR=greenhouse
export EXEC_RADAR_GREENHOUSE_BOARD=stripe
python -m apps.worker.main
```

With database persistence:
```bash
export EXEC_RADAR_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/exec_radar
alembic upgrade head
python -m apps.worker.main
```

## Testing

### All unit tests

```bash
pytest -v
```

### Specific test

```bash
pytest tests/test_greenhouse_collector.py::test_returns_raw_postings -v
```

### GUI tests (requires Playwright)

```bash
pytest tests/e2e/ -v
```

### Coverage

```bash
pytest --cov=packages tests/
```

### Watch mode (auto-rerun on changes)

```bash
pytest-watch tests/
```

## API

### Health check

```bash
curl http://localhost:8000/health
```

### List jobs (default: 10)

```bash
curl http://localhost:8000/jobs | jq '.jobs[0:5]'
```

### Filter by score > 50%

```bash
curl http://localhost:8000/jobs | jq '.jobs[] | select(.score.overall > 0.5)'
```

### Get single job details

```bash
JOB_ID=$(curl -s http://localhost:8000/jobs | jq -r '.jobs[0].job.id')
curl http://localhost:8000/jobs | jq ".jobs[] | select(.job.id == \"$JOB_ID\")"
```

### Mark as favorite

```bash
curl -X POST http://localhost:8000/dashboard/preferences/toggle \
  -H "Content-Type: application/json" \
  -d '{"user_id":"default","job_id":"job-123","action":"favorite"}'
```

### Get favorites

```bash
curl http://localhost:8000/dashboard/preferences?user_id=default | jq '.favorites'
```

## Database

### Initialize PostgreSQL

```bash
export EXEC_RADAR_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/exec_radar

# Create migrations
alembic upgrade head

# Check current state
alembic current
```

### Reset database

```bash
alembic downgrade base
alembic upgrade head
```

### Create new migration

```bash
alembic revision --autogenerate -m "Description"
```

## Code Quality

### Format & lint

```bash
ruff check . --fix
ruff format .
```

### Type check

```bash
mypy packages/ --strict
```

### Run all checks

```bash
ruff check . && ruff format . && pytest -v
```

## Docker

### Build image

```bash
docker build -t exec-radar .
```

### Run with mock data

```bash
docker run -p 8000:8000 exec-radar
```

### Run with Greenhouse

```bash
docker run -p 8000:8000 \
  -e EXEC_RADAR_COLLECTOR=greenhouse \
  -e EXEC_RADAR_GREENHOUSE_BOARD=discord \
  exec-radar
```

### Run with database

```bash
docker run -p 8000:8000 \
  -e EXEC_RADAR_DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/exec_radar \
  exec-radar
```

## Development Workflows

### Add a new collector

1. Create `packages/collectors/your_collector.py`
2. Extend `BaseCollector`
3. Implement `source_name` and `collect()`
4. Add tests in `tests/test_your_collector.py`
5. Register in `packages/services.py`
6. Document in README.md

Example:
```python
from packages.collectors.base import BaseCollector
from packages.schemas.raw_job import RawJobPosting

class YourCollector(BaseCollector):
    @property
    def source_name(self) -> str:
        return "your_source"

    async def collect(self) -> list[RawJobPosting]:
        # Fetch and return jobs
        pass
```

### Update target profile

Edit `examples/sample_profile.yaml`:

```yaml
target_titles:
  - chief operating officer
  - vp of operations

target_seniority: [c_level, svp, vp]

target_locations:
  - New York
  - London

required_keywords:
  - operations
  - supply chain

weight_title: 0.35
weight_seniority: 0.25
weight_location: 0.15
weight_skills: 0.25
```

Then run:
```bash
export EXEC_RADAR_TARGET_PROFILE=examples/sample_profile.yaml
python -m apps.worker.main
```

### Debug a specific job

```bash
# Get the job
JOB_ID=$(curl -s http://localhost:8000/jobs | jq -r '.jobs[0].job.id')

# View full details
curl -s http://localhost:8000/jobs | jq ".jobs[] | select(.job.id == \"$JOB_ID\")"

# In Python (for debugging)
python -c "
import asyncio
from packages.services import build_pipeline_components
from packages.pipeline import run_pipeline

async def test():
    collector, normalizer, ranker = build_pipeline_components()
    jobs = await run_pipeline(collector, normalizer, ranker)
    target_job = next((j for j in jobs if j.job.id == '$JOB_ID'), None)
    if target_job:
        print(f'Title match: {target_job.score.title_match}')
        print(f'Explanation: {target_job.score.explanation}')

asyncio.run(test())
"
```

### Check logs

```bash
# API server logs
tail -f /tmp/api.log

# Worker logs
python -m apps.worker.main 2>&1 | grep ERROR
```

## Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `EXEC_RADAR_COLLECTOR` | `greenhouse` | Collector: `mock` or `greenhouse` |
| `EXEC_RADAR_GREENHOUSE_BOARD` | `discord` | Greenhouse board token |
| `EXEC_RADAR_TARGET_PROFILE` | `./my_profile.yaml` | Path to profile file |
| `EXEC_RADAR_DATABASE_URL` | `postgresql+asyncpg://...` | Database connection |
| `LOG_LEVEL` | `DEBUG` | Logging: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Troubleshooting

### "Module not found: packages"

```bash
# Make sure you're in the repo root
cd /path/to/exec-radar

# Reinstall
pip install -e .
```

### "Cannot import BaseCollector"

```bash
# Check Python path
python -c "import packages.collectors.base"

# Or run from repo root
cd /path/to/exec-radar
python -m apps.api.main
```

### Tests fail with "event loop"

```bash
# Run unit tests and E2E separately
pytest tests/ -v          # Unit tests
pytest tests/e2e/ -v      # E2E tests
```

### Dashboard shows no jobs

1. Check collector is running: `EXEC_RADAR_COLLECTOR=greenhouse python -m apps.worker.main`
2. Check board token: `curl https://boards-api.greenhouse.io/v1/boards/discord/jobs`
3. Check logs for errors

### PostgreSQL connection refused

```bash
# Check if postgres is running
psql -U postgres -d postgres -c "SELECT 1"

# Create database if needed
createdb exec_radar

# Run migrations
alembic upgrade head
```

## Resources

- **User Docs**: [README.md](README.md)
- **Developer Docs**: [DEVELOPMENT.md](DEVELOPMENT.md)
- **API Docs**: [API.md](API.md)
- **Architecture**: [docs/architecture.md](docs/architecture.md)
- **Roadmap**: [docs/roadmap.md](docs/roadmap.md)

## Getting Help

1. Check [DEVELOPMENT.md#troubleshooting](DEVELOPMENT.md#troubleshooting)
2. Review test examples in `tests/`
3. Run with `LOG_LEVEL=DEBUG` for more output
4. Check GitHub issues for similar problems
