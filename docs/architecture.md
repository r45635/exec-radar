# Architecture

## Overview

Exec Radar is a Python monorepo organised around three distinct processing stages:

```
[Sources] → Collectors → RawJobPosting
                              ↓
                         Normalizers → NormalizedJobPosting
                                              ↓
                                         Rankers → FitScore
                                                       ↓
                                               API / Dashboard
```

Each stage is a separate Python package under `packages/`, allowing independent
development, testing, and replacement of components.

---

## Repository layout

```
exec-radar/
├── apps/
│   ├── api/          # FastAPI service – exposes job data and scores
│   ├── worker/       # Background job – runs the collect → normalize → score pipeline
│   └── dashboard/    # Placeholder dashboard (future milestone)
├── packages/
│   ├── schemas/      # Shared Pydantic models (RawJobPosting, NormalizedJobPosting, FitScore)
│   ├── collectors/   # Source adapters (BaseCollector, HttpCollector, MockCollector)
│   ├── normalizers/  # Normalisation logic (BaseNormalizer, SimpleNormalizer)
│   ├── rankers/      # Scoring logic (BaseRanker, ExecutiveProfile, RuleBasedRanker)
│   └── notifications/ # Notification interfaces (BaseNotifier)
├── tests/            # pytest test suite
├── docs/             # Architecture and roadmap documents
└── .github/          # GitHub configuration and Copilot instructions
```

---

## Data flow

### 1. Collection (`packages/collectors`)

A **Collector** fetches raw job postings from a single external source.  It
implements `BaseCollector.collect()` which returns `list[RawJobPosting]`.

- `MockCollector` – returns hard-coded sample data; used in tests and local dev.
- `HttpCollector` – fetches from a configurable JSON endpoint.
- Future: `PlaywrightCollector` for JavaScript-rendered pages,
  `RSSCollector` for RSS/Atom feeds.

### 2. Normalisation (`packages/normalizers`)

A **Normalizer** converts a `RawJobPosting` into a `NormalizedJobPosting` using
a canonical schema.  It applies:

- Title cleaning and whitespace normalisation
- Seniority level inference (keyword matching)
- Employment type inference
- Remote detection
- Salary range parsing
- Skill and keyword extraction

The current `SimpleNormalizer` uses regex and keyword lists.  Future
implementations can use LLMs or spaCy for richer extraction.

### 3. Scoring (`packages/rankers`)

A **Ranker** scores a `NormalizedJobPosting` against an `ExecutiveProfile` and
returns a `FitScore` with an overall score (0–100) and per-dimension breakdown:

| Dimension    | Weight | Description                         |
|:-------------|:------:|:------------------------------------|
| Title        |  35 %  | Keyword and seniority match         |
| Skills       |  30 %  | Required + preferred skill overlap  |
| Location     |  20 %  | Remote preference and city match    |
| Compensation |  15 %  | Salary range alignment              |

The `RuleBasedRanker` implements this using simple arithmetic.  Future rankers
can use sentence embeddings for semantic similarity.

### 4. API (`apps/api`)

A FastAPI application exposes:

| Method | Path                        | Description                |
|:-------|:----------------------------|:---------------------------|
| GET    | `/health`                   | Liveness probe             |
| GET    | `/api/v1/jobs`              | Paginated job list         |
| GET    | `/api/v1/jobs/{id}`         | Single job posting         |
| GET    | `/api/v1/jobs/{id}/score`   | Fit score for a job        |
| POST   | `/api/v1/jobs/ingest`       | Ingest a raw posting       |

The in-memory store will be replaced with a PostgreSQL repository.

### 5. Worker (`apps/worker`)

A standalone async Python script that runs the pipeline on a configurable
interval.  It will be extended to support:

- Multiple collectors running concurrently
- Idempotent upserts to PostgreSQL
- Notifications for high-scoring jobs

---

## Key design principles

- **Separation of concerns** – collection, normalisation, and scoring are
  independent layers that can be swapped without affecting others.
- **Type safety** – every public API uses type hints and Pydantic v2 validation.
- **Extensibility** – abstract base classes make it straightforward to add new
  sources, normalizers, and rankers.
- **Testability** – `MockCollector` and in-memory stores allow full-stack tests
  without external dependencies.
