"""E2E test fixtures — Playwright server and config."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Generator

import pytest

_PORT = 18765


@pytest.fixture(scope="session")
def base_url() -> Generator[str, None, None]:
    """Start the FastAPI app in a subprocess and return the base URL."""
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(_PORT),
            "--log-level",
            "error",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import httpx

    url = f"http://127.0.0.1:{_PORT}"
    for _ in range(40):
        try:
            r = httpx.get(f"{url}/health", timeout=1)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("Test server did not start in time")
    yield url
    proc.terminate()
    proc.wait(timeout=5)
