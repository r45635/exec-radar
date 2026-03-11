"""Job state tracking utilities.

Classify jobs as new, seen, or updated based on stable identity and content changes.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.schemas.normalized_job import NormalizedJobPosting

# Job state constants
JOB_STATE_NEW = "new"
JOB_STATE_SEEN = "seen"
JOB_STATE_UPDATED = "updated"


def compute_content_hash(job: NormalizedJobPosting) -> str:
    """Compute a hash of meaningful job content for change detection.

    Hash is based on:
    - title
    - description_plain
    - salary_min, salary_max, salary_currency
    - tags

    This captures meaningful updates while ignoring metadata like timestamps.

    Args:
        job: The normalized job posting.

    Returns:
        SHA256 hex digest of the content.
    """
    content = {
        "title": job.title,
        "description": job.description_plain,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "tags": sorted(job.tags),
    }
    content_json = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content_json.encode()).hexdigest()


def classify_job_state(
    is_new: bool,
    previous_hash: str | None,
    current_hash: str,
) -> str:
    """Classify a job's state based on existence and content changes.

    Args:
        is_new: True if this is the first time we've seen this job_id.
        previous_hash: The stored hash from the previous run (if any).
        current_hash: The freshly computed hash.

    Returns:
        One of: "new", "seen", "updated"
    """
    if is_new:
        return JOB_STATE_NEW

    if previous_hash is None or previous_hash == "":
        # No previous hash (shouldn't happen, but treat as new)
        return JOB_STATE_NEW

    if previous_hash == current_hash:
        return JOB_STATE_SEEN

    return JOB_STATE_UPDATED
