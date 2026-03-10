# Roadmap

## Current state – v0.1 (Foundation)

✅ Monorepo scaffold with clean package boundaries  
✅ Shared Pydantic v2 schemas (RawJobPosting, NormalizedJobPosting, FitScore)  
✅ Collector interfaces + MockCollector + HttpCollector  
✅ Normalizer interface + SimpleNormalizer (regex / keyword)  
✅ Ranker interface + RuleBasedRanker (weighted scoring)  
✅ FastAPI app with health, list, get, and ingest endpoints  
✅ Background worker prototype  
✅ pytest test suite  
✅ Dockerfile + docker-compose  

---

## Milestone 1 – Persistence (v0.2)

- [ ] Add SQLAlchemy 2.x async models for `NormalizedJobPosting` and `FitScore`
- [ ] Implement PostgreSQL repository classes
- [ ] Alembic migrations
- [ ] Replace in-memory job store in the API with the real repository
- [ ] Add `DATABASE_URL` validation on startup

---

## Milestone 2 – Real collectors (v0.3)

- [ ] `PlaywrightCollector` – scrape JavaScript-rendered pages with Playwright
- [ ] `RSSCollector` – parse RSS/Atom feeds from job boards
- [ ] Configurable collector registry loaded from YAML / environment
- [ ] Deduplication logic (hash-based, by `source` + `source_id`)
- [ ] Rate limiting and retry logic

---

## Milestone 3 – Semantic ranking (v0.4)

- [ ] `EmbeddingRanker` – score postings using sentence-transformer embeddings
- [ ] Store embeddings alongside normalized postings in PostgreSQL (pgvector)
- [ ] Similarity search endpoint: "find jobs like this one"
- [ ] Optional OpenAI GPT integration for explanation generation

---

## Milestone 4 – Dashboard (v0.5)

- [ ] Choose and scaffold UI framework (Streamlit / Next.js / HTMX)
- [ ] Job feed with fit score badges and seniority chips
- [ ] Filter bar: seniority, location, remote, salary, skills
- [ ] Score breakdown modal
- [ ] Executive profile editor (desired titles, skills, salary, location)

---

## Milestone 5 – Notifications (v0.6)

- [ ] `EmailNotifier` – send digest emails via SMTP
- [ ] `SlackNotifier` – post to a Slack channel via webhook
- [ ] Configurable thresholds (notify when score ≥ N)
- [ ] Daily / weekly digest mode

---

## Milestone 6 – Production hardening (v1.0)

- [ ] Authentication (API key or OAuth2) on the API
- [ ] Prometheus metrics + Grafana dashboard
- [ ] Structured JSON logging
- [ ] Kubernetes manifests (Deployment, Service, CronJob for worker)
- [ ] CI/CD pipeline (GitHub Actions: lint → test → build → deploy)
- [ ] Secrets management (no plaintext `.env` in production)
- [ ] Load testing and performance benchmarks

---

## Ideas backlog

- LinkedIn / Indeed / Greenhouse integrations
- Chrome extension to score jobs while browsing
- Executive profile versioning (track score changes over time)
- Collaborative profiles for executive search firms
- NLP-based requirement extraction (spaCy / LLM)
- Market salary analytics across collected postings
