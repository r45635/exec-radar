# API Reference

Complete documentation for Exec Radar's REST API.

## Base URL

```
http://localhost:8000
```

## Endpoints

### Health Check

**GET** `/health`

Returns API status and version.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

**Status codes:**
- `200 OK` — Service is healthy
- `500 Internal Server Error` — Service unavailable

---

### List Scored Jobs

**GET** `/jobs`

Returns paginated list of jobs scored against the target profile, sorted by fit score (highest first).

```bash
curl http://localhost:8000/jobs
```

**Response:**
```json
{
  "count": 84,
  "jobs": [
    {
      "job": {
        "id": "d649ac90d0caaa9f1047e7440656a9f2",
        "source": "greenhouse:cloudflare",
        "source_id": "7601801",
        "source_url": "https://boards.greenhouse.io/cloudflare/jobs/7601801",
        "title": "Field CTO, Greater China",
        "company": null,
        "location": "Hybrid",
        "remote_policy": "hybrid",
        "seniority": "c_level",
        "description_plain": "...",
        "salary_min": null,
        "salary_max": null,
        "salary_currency": null,
        "tags": ["digital", "operations", "transformation"],
        "posted_at": "2026-02-12T23:08:01-05:00",
        "normalized_at": "2026-03-10T22:39:56.067379Z"
      },
      "score": {
        "job_id": "d649ac90d0caaa9f1047e7440656a9f2",
        "overall": 0.4625,
        "title_match": 0.0,
        "seniority_match": 1.0,
        "location_match": 1.0,
        "skills_match": 0.25,
        "explanation": "Seniority and location match well; title differs"
      }
    }
  ]
}
```

**Response fields:**
- `count` — Total number of jobs
- `jobs` — Array of ScoredJobPosting objects
  - `job` — NormalizedJobPosting with all job details
  - `score` — FitScore with overall and per-dimension scores
  - `job_state` — State of the job: `"new"`, `"seen"`, or `"updated"` (see Job State section below)

**Status codes:**
- `200 OK` — Success
- `500 Internal Server Error` — Failed to fetch/score jobs

---

## Dashboard Endpoints

### Get Preferences

**GET** `/dashboard/preferences?user_id=default`

Returns user's favorites and dismissed jobs.

```bash
curl http://localhost:8000/dashboard/preferences?user_id=default
```

**Response:**
```json
{
  "user_id": "default",
  "favorites": ["job-id-1", "job-id-2"],
  "dismissed": ["job-id-3"]
}
```

**Parameters:**
- `user_id` (query) — User identifier (default: `"default"`)

**Status codes:**
- `200 OK` — Success

---

### Toggle Preference

**POST** `/dashboard/preferences/toggle`

Mark a job as favorite or dismissed.

```bash
curl -X POST http://localhost:8000/dashboard/preferences/toggle \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "default",
    "job_id": "d649ac90d0caaa9f1047e7440656a9f2",
    "action": "favorite"
  }'
```

**Request body:**
```json
{
  "user_id": "default",
  "job_id": "d649ac90d0caaa9f1047e7440656a9f2",
  "action": "favorite"  // or "dismissed"
}
```

**Response:**
```json
{
  "user_id": "default",
  "job_id": "d649ac90d0caaa9f1047e7440656a9f2",
  "favorited": true,
  "dismissed": false
}
```

**Parameters:**
- `user_id` (body) — User identifier (default: `"default"`)
- `job_id` (body) — Job ID to toggle
- `action` (body) — `"favorite"` or `"dismissed"`

**Status codes:**
- `200 OK` — Success
- `400 Bad Request` — Invalid action or job_id
- `500 Internal Server Error` — Database error

**Behavior:**
- Toggling the same preference twice removes it
- Favoriting a dismissed job removes dismiss status (and vice versa)
- Changes persist to local dashboard database

---

## Dashboard UI

**GET** `/dashboard/`

Returns HTML dashboard with jobs table and detail panel.

Accessible at: http://localhost:8000/dashboard/

Features:
- Search (title, company, location)
- Filters (seniority, remote, status)
- Sort by score, title, company, date
- Pagination / virtual scroll
- Table and card view toggle
- Job detail panel with full description
- Favorites and dismissed tracking

---

## Data Types

### RemotePolicy

Enum: `"remote"`, `"hybrid"`, `"onsite"`, `"unknown"`

### Seniority

Enum: `"c_level"`, `"vp"`, `"svp"`, `"director"`, `"head"`, `"other"`

### NormalizedJobPosting

```python
{
  "id": str,                          # Hash of (source, source_id)
  "source": str,                      # "greenhouse:discord", "mock"
  "source_id": str,                   # ID within source
  "source_url": str | null,           # Direct link to posting
  "title": str,                       # Job title
  "company": str | null,              # Company name
  "location": str | null,             # Location (parsed)
  "remote_policy": RemotePolicy,      # remote/hybrid/onsite
  "seniority": Seniority,             # c_level/vp/svp/director/head/other
  "description_plain": str,           # HTML parsed to plain text
  "salary_min": int | null,           # Parsed salary (USD cents)
  "salary_max": int | null,           # Parsed salary (USD cents)
  "salary_currency": str | null,      # "USD", "EUR", etc.
  "tags": [str],                      # Extracted keywords
  "posted_at": datetime | null,       # Original post date
  "normalized_at": datetime           # When normalized
}
```

### FitScore

```python
{
  "job_id": str,
  "overall": float,                   # 0.0 - 1.0
  "title_match": float,               # 0.0 - 1.0
  "seniority_match": float,           # 0.0 - 1.0
  "location_match": float,            # 0.0 - 1.0
  "skills_match": float,              # 0.0 - 1.0
  "explanation": str                  # Human-readable summary
}
```

### JobState

A job's state indicates whether it is new, previously seen, or recently updated:

- **`"new"`** — First time this job (source, source_id) appears in the pipeline
- **`"seen"`** — Previously seen and content is unchanged (same title, description, salary, tags)
- **`"updated"`** — Previously seen but content changed (title, description, salary, or tags differ)

The state is determined by comparing a hash of content fields. Metadata changes (location, remote_policy, seniority) don't affect state.

**Use cases:**
- Filter for only new jobs
- Highlight updates to jobs you're tracking
- Avoid re-reading job descriptions you've already reviewed

---

## Examples

### Get top 5 jobs

```bash
curl http://localhost:8000/jobs | jq '.jobs[0:5]'
```

### Search by fit score threshold

```bash
curl http://localhost:8000/jobs | jq '.jobs[] | select(.score.overall > 0.7)'
```

### Get all C-level positions

```bash
curl http://localhost:8000/jobs | jq '.jobs[] | select(.job.seniority == "c_level")'
```

### Filter by job state (new, seen, updated)

```bash
# Only new jobs (first time seen)
curl http://localhost:8000/jobs | jq '.jobs[] | select(.job_state == "new")'

# Updated jobs (content changed since last run)
curl http://localhost:8000/jobs | jq '.jobs[] | select(.job_state == "updated")'

# Previously seen jobs (unchanged)
curl http://localhost:8000/jobs | jq '.jobs[] | select(.job_state == "seen")'
```

### Mark top job as favorite

```bash
TOP_JOB_ID=$(curl -s http://localhost:8000/jobs | jq -r '.jobs[0].job.id')
curl -X POST http://localhost:8000/dashboard/preferences/toggle \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"default\", \"job_id\": \"$TOP_JOB_ID\", \"action\": \"favorite\"}"
```

### Get all favorites

```bash
curl http://localhost:8000/dashboard/preferences?user_id=default | jq '.favorites'
```

---

## Error Handling

All errors return JSON with `detail` field:

```json
{
  "detail": "Invalid action: must be 'favorite' or 'dismissed'"
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Not found |
| 500 | Server error (see logs) |

---

## Rate Limiting

Currently unlimited. Future versions may add rate limiting per user.

---

## Pagination

Currently not implemented in `/jobs`. All results returned in one response.

Future versions will support:
- `?limit=50&offset=0`
- `?limit=50&page=1`

---

## Authentication

Currently no authentication. Future versions will support API keys for multi-user deployments.

---

## CORS

CORS is not enabled. For cross-origin requests, deploy behind a proxy (nginx, Cloudflare, etc.).

---

## Webhooks

Not yet implemented. Coming soon for real-time notifications.
