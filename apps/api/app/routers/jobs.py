"""Jobs API endpoints – list, retrieve, and score job postings."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from schemas import FitScore, NormalizedJobPosting, RawJobPosting
from schemas.normalized_job_posting import SeniorityLevel

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory store – replace with a real database repository in production.
# ---------------------------------------------------------------------------
_jobs_store: dict[str, NormalizedJobPosting] = {}
_scores_store: dict[str, FitScore] = {}


class JobsListResponse(BaseModel):
    """Paginated list of normalized job postings."""

    total: int
    jobs: list[NormalizedJobPosting]


class IngestRequest(BaseModel):
    """Request body for ingesting a raw job posting via the API."""

    raw: RawJobPosting


class ScoreResponse(BaseModel):
    """Fit score for a specific job."""

    job_id: str
    score: FitScore | None


def _seed_demo_data() -> None:
    """Populate the in-memory store with demo data on first import.

    This is a temporary measure to make the API useful out of the box.
    Remove when real persistence is added.
    """
    from datetime import datetime

    demo_jobs = [
        NormalizedJobPosting(
            id="demo-001",
            source="mock",
            source_id="mock-001",
            url="https://example.com/jobs/cto-001",  # type: ignore[arg-type]
            title="Chief Technology Officer",
            seniority=SeniorityLevel.C_SUITE,
            company="Acme Corp",
            location="San Francisco, CA",
            remote=True,
            salary_min=250_000.0,
            salary_max=320_000.0,
            skills=["python", "aws", "leadership"],
            keywords=["cto", "engineering", "technology"],
            posted_at=datetime(2024, 1, 15, 10, 0, 0),
        ),
        NormalizedJobPosting(
            id="demo-002",
            source="mock",
            source_id="mock-002",
            url="https://example.com/jobs/vp-eng-002",  # type: ignore[arg-type]
            title="VP of Engineering",
            seniority=SeniorityLevel.VP,
            company="TechStartup Inc.",
            location="New York, NY",
            remote=False,
            salary_min=200_000.0,
            salary_max=250_000.0,
            skills=["leadership", "aws", "kubernetes"],
            keywords=["vp", "engineering", "scaling"],
            posted_at=datetime(2024, 1, 16, 8, 30, 0),
        ),
    ]
    for job in demo_jobs:
        _jobs_store[job.id] = job


_seed_demo_data()


@router.get("/jobs", response_model=JobsListResponse, summary="List job postings")
async def list_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    seniority: SeniorityLevel | None = Query(None, description="Filter by seniority level"),
) -> JobsListResponse:
    """Return a paginated list of normalized job postings.

    Optionally filter by ``seniority`` level.
    """
    jobs = list(_jobs_store.values())
    if seniority:
        jobs = [j for j in jobs if j.seniority == seniority]
    total = len(jobs)
    return JobsListResponse(total=total, jobs=jobs[skip : skip + limit])


@router.get("/jobs/{job_id}", response_model=NormalizedJobPosting, summary="Get a job posting")
async def get_job(job_id: str) -> NormalizedJobPosting:
    """Return a single normalized job posting by its ID."""
    job = _jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get(
    "/jobs/{job_id}/score",
    response_model=ScoreResponse,
    summary="Get fit score for a job",
)
async def get_job_score(job_id: str) -> ScoreResponse:
    """Return the latest fit score for a job posting (if available)."""
    if job_id not in _jobs_store:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return ScoreResponse(job_id=job_id, score=_scores_store.get(job_id))


@router.post(
    "/jobs/ingest",
    response_model=NormalizedJobPosting,
    status_code=201,
    summary="Ingest a raw job posting",
)
async def ingest_job(request: IngestRequest) -> NormalizedJobPosting:
    """Ingest a raw job posting, normalize it, and store it.

    This endpoint is primarily for development and testing.  In production,
    the worker service runs the collection and normalization pipeline.
    """
    from normalizers import SimpleNormalizer

    normalizer = SimpleNormalizer()
    normalized = normalizer.normalize(request.raw)
    _jobs_store[normalized.id] = normalized
    return normalized
