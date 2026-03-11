# Exec Radar

**AI-powered executive opportunity intelligence platform**

Exec Radar continuously scans public job sources for executive and senior operations opportunities, scores them against your profile, and surfaces the most relevant roles through an interactive dashboard and REST API.

## Features

- 🎯 **Smart Matching** — Scores job postings against your target profile (titles, seniority, locations, skills)
- 🌐 **Multi-Source** — Fetches from Greenhouse, Lever, and Ashby ATS platforms in parallel
- 📊 **Interactive Dashboard** — Table and card views, filters, search, favorites, detailed panels
- 🔄 **Real-Time Updates** — Continuous pipeline to keep opportunities fresh
- 🔍 **State Tracking** — Automatically marks jobs as new, seen, or updated (based on content changes)
- 💾 **Persistence** — Optional database storage for historical tracking
- 🚀 **Simple Deployment** — Docker-ready, single API server with embedded dashboard

## Scoring Engine

Exec Radar scores each posting across **six weighted dimensions**:

| Dimension | Description |
|-----------|-------------|
| **Title** | Target / adjacent / excluded title matching with family awareness |
| **Seniority** | C-level, VP, Director alignment |
| **Industry** | Target and adjacent industry overlap |
| **Scope** | Executive scope indicators (multi-site, global, P&L) |
| **Geography** | Location + remote policy fit |
| **Keyword Clusters** | Domain cluster overlap across five clusters |

### Keyword Clusters

| Cluster | Focus |
|---------|-------|
| `semiconductor_manufacturing` | Wafer, fab, cleanroom, yield, process engineering |
| `fabless_foundry_osat` | Fabless, foundry, OSAT, contract manufacturing, advanced packaging, supplier quality |
| `automotive_quality` | IATF 16949, APQP, PPAP, FMEA, OEM |
| `executive_operations_leadership` | P&L, transformation, lean, six sigma, operational excellence |
| `supply_chain_industrialization` | Supply chain, NPI, industrialization, ramp-up, S&OP |

### Stricter Scoring Penalties

The ranker applies post-scoring penalties to reduce noise:

- **Software-heavy** — Roles with multiple software/devops/SaaS signals are demoted
- **GTM / business-only** — Revenue ops, demand gen, sales enablement roles are penalized
- **Misleading ops titles** — Operations titles without manufacturing/SC/industrial evidence are flagged
- **Too junior** — Intern, junior, trainee roles receive a hard multiplier
- **Narrow scope** — Single-site/plant roles are penalized (×0.50) when the profile targets executive/global scope
- **Exec semiconductor bonus** — Postings with ≥4 exec-semi signals (foundry, OSAT, NPI, ramp, multi-site, etc.) get a ×1.15 boost; ≥2 signals get ×1.08

Each penalty and bonus is deterministic and appears in `why_penalized` / `why_matched` / `red_flags` for full explainability.

### Named Source Sets

Pre-configured board collections you can assign to a profile:

| Source Set | Focus | Sources |
|------------|-------|--------|
| `semiconductor_exec` | IDM, fabless, foundry, OSAT execs | 12 Greenhouse + 2 Lever + 2 Ashby |
| `deeptech_hardware` | AI-chip & advanced computing | 8 Greenhouse + 2 Lever + 2 Ashby |
| `broad_exec_ops` | Cross-industry exec operations | 10 Greenhouse + 2 Lever + 2 Ashby |

Set via profile dropdown, `preferred_source_set` in YAML, or `EXEC_RADAR_SOURCE_SET` env var.

### Multi-Profile Comparison

The **Compare** page (`/dashboard/compare`) lets you pick two profiles and see the same jobs scored side-by-side, sorted by absolute score delta. Useful for tuning profile keywords without guesswork.

## Quick Start

### 1. Install

```bash
git clone https://github.com/r45635/exec-radar.git
cd exec-radar
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Start with Mock Data

```bash
uvicorn apps.api.main:app --reload
```

Then open **[http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)** in your browser.

### 3. Configure Your Target Profile

Edit `examples/sample_profile.yaml` to define your ideal role:

```yaml
target_titles:
  - chief operating officer
  - vp of operations

target_seniority: [c_level, svp, vp]
target_locations: [New York, London, Remote]
required_keywords: [operations, supply chain, strategy]

# Scoring weights
weight_title: 0.35
weight_seniority: 0.25
weight_location: 0.15
weight_skills: 0.25
```

### 4. Use Real Job Sources

Switch to the **Greenhouse Boards API** (covers 1000+ companies with public careers pages):

```bash
# Default: scans 6 semiconductor companies (Lattice, Tenstorrent, Graphcore, Lightmatter, SambaNova, Cerebras)
export EXEC_RADAR_COLLECTOR=greenhouse
uvicorn apps.api.main:app --reload

# Or target specific companies (comma-separated board tokens)
export EXEC_RADAR_COLLECTOR=greenhouse
export EXEC_RADAR_GREENHOUSE_BOARDS=lattice,tenstorrent,cerebrassystems
uvicorn apps.api.main:app --reload

# Or a single board
export EXEC_RADAR_COLLECTOR=greenhouse
export EXEC_RADAR_GREENHOUSE_BOARD=discord
uvicorn apps.api.main:app --reload
```

The dashboard will now show real opportunities scored against your active profile.

## Usage

### Dashboard

Access at `/dashboard` with:
- **Search** — Find roles by title, company, location
- **Filters** — By seniority, remote policy, status (active/favorites/dismissed)
- **Toggle Views** — Table for detailed comparison, cards for browsing
- **Pagination** — Efficient viewing of large lists
- **Detail Panel** — Click any job to see full description and scoring breakdown
- **Preferences** — Mark jobs as favorites or dismissed (persists locally)

### API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# List scored jobs
curl http://localhost:8000/jobs | jq '.jobs[0:5]'

# Dashboard preferences (local to browser)
curl http://localhost:8000/dashboard/preferences?user_id=default
```

### Command Line: Run Pipeline Once

```bash
python -m apps.worker.main
```

Fetches jobs, scores them, and logs results. Add persistence:

```bash
export EXEC_RADAR_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/exec_radar
alembic upgrade head
python -m apps.worker.main
```

## Deployment

### Docker

```bash
docker build -t exec-radar .
docker run -p 8000:8000 \
  -e EXEC_RADAR_COLLECTOR=greenhouse \
  -e EXEC_RADAR_GREENHOUSE_BOARD=stripe \
  exec-radar
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXEC_RADAR_COLLECTOR` | `mock` | `mock`, `greenhouse`, `lever`, `ashby`, `all`, or `greenhouse+lever+ashby` |
| `EXEC_RADAR_GREENHOUSE_BOARDS` | *(12 semi boards)* | Comma-separated Greenhouse board tokens |
| `EXEC_RADAR_GREENHOUSE_BOARD` | — | Single Greenhouse board token (fallback) |
| `EXEC_RADAR_LEVER_COMPANY` | — | Lever company slug(s), comma-separated |
| `EXEC_RADAR_ASHBY_COMPANY` | — | Ashby company slug(s), comma-separated |
| `EXEC_RADAR_SOURCE_SET` | — | Named source set (`semiconductor_exec`, `deeptech_hardware`, `broad_exec_ops`) |
| `EXEC_RADAR_TARGET_PROFILE` | — | Path to YAML profile file |
| `EXEC_RADAR_DATABASE_URL` | — | PostgreSQL or MySQL URL for persistence |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Database Setup (Optional)

For persistent job storage:

```bash
export EXEC_RADAR_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/exec_radar
alembic upgrade head
python -m apps.worker.main
```

Supported databases: PostgreSQL (recommended), MySQL, SQLite (development only).

## Job Sources

### Mock Collector (Built-in)

Five sample executive postings. Perfect for testing and demos. No configuration needed.

```bash
export EXEC_RADAR_COLLECTOR=mock  # Default
```

### Greenhouse

Public job listings from 1000+ companies using Greenhouse ATS. No API keys required.

```bash
export EXEC_RADAR_COLLECTOR=greenhouse
# Defaults to 6 semiconductor boards if no boards specified
```

**Built-in semiconductor boards:**

| Token | Company | ~Jobs |
|-------|---------|-------|
| `lattice` | Lattice Semiconductor | 18 |
| `tenstorrent` | Tenstorrent | 109 |
| `graphcore` | Graphcore | 128 |
| `lightmatter` | Lightmatter | 56 |
| `sambanovasystems` | SambaNova Systems | 13 |
| `cerebrassystems` | Cerebras Systems | 92 |

Multiple boards are fetched in parallel via the `CompositeCollector`.

Other popular board tokens: `discord`, `cloudflare`, `figma`, `notion`, `stripe`, `remote`.

### Lever

Public job listings from companies using the Lever ATS. No API keys required.

```bash
# Single company
export EXEC_RADAR_COLLECTOR=lever
export EXEC_RADAR_LEVER_COMPANY=netflix
uvicorn apps.api.main:app --reload

# Multiple companies (comma-separated)
export EXEC_RADAR_COLLECTOR=lever
export EXEC_RADAR_LEVER_COMPANY=netflix,twitch,datadog
uvicorn apps.api.main:app --reload
```

Uses the Lever Postings API: `https://api.lever.co/v0/postings/<company>?mode=json`

Popular company slugs: `netflix`, `twitch`, `datadog`, `coinbase`, `lever`.

Multiple slugs are fetched in parallel via the `CompositeCollector`.

### Ashby

Public job listings from companies using the Ashby ATS. No API keys required.

```bash
# Single company
export EXEC_RADAR_COLLECTOR=ashby
export EXEC_RADAR_ASHBY_COMPANY=ramp
uvicorn apps.api.main:app --reload

# Multiple companies (comma-separated)
export EXEC_RADAR_COLLECTOR=ashby
export EXEC_RADAR_ASHBY_COMPANY=ramp,notion,cohere
uvicorn apps.api.main:app --reload
```

Extracts job data from the embedded `window.__appData` JSON on Ashby career pages.

Popular company slugs: `ramp`, `notion`, `linear`, `cohere`.

Multiple slugs are fetched in parallel via the `CompositeCollector`.

### Multi-Source Collection

Combine multiple ATS types in a single run:

```bash
# Combine specific sources
export EXEC_RADAR_COLLECTOR=greenhouse+lever+ashby
export EXEC_RADAR_GREENHOUSE_BOARD=lattice,tenstorrent
export EXEC_RADAR_LEVER_COMPANY=rigetti,aeva
export EXEC_RADAR_ASHBY_COMPANY=ramp,cohere
uvicorn apps.api.main:app --reload

# Or use "all" with a named source set
export EXEC_RADAR_COLLECTOR=all
export EXEC_RADAR_SOURCE_SET=semiconductor_exec
uvicorn apps.api.main:app --reload
```

**Coming soon:** LinkedIn, Indeed, custom RSS feeds, email alerts.

## FAQ

**Q: Does this scrape websites?**
A: No. Greenhouse and Lever use public JSON APIs. Ashby data is extracted from public HTML career pages (embedded JSON). No browser automation.

**Q: Is my profile private?**
A: Yes. When run locally, everything stays on your machine. Optional database is your own infrastructure.

**Q: What are "new", "seen", and "updated" jobs?**
A: Exec Radar tracks job state:
- **new** — First time this job appears (never seen before)
- **seen** — Job seen before with unchanged content (same title, description, salary, tags)
- **updated** — Job seen before but content changed (title, description, salary, or tags differ)

Use the API to filter: `curl http://localhost:8000/jobs | jq '.jobs[] | select(.job_state == "new")'`

**Q: Can I add custom job sources?**
A: Yes. See [DEVELOPMENT.md](DEVELOPMENT.md#adding-a-collector) to build a new collector.

**Q: How often are jobs updated?**
A: In current version, manually on-demand via `apps.worker.main`. Scheduled polling coming soon.

## License

MIT

---

**For developers:** See [DEVELOPMENT.md](DEVELOPMENT.md) for setup, testing, architecture, and extending Exec Radar.
