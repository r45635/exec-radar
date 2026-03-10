"""Entry point for the Exec Radar API server."""

import uvicorn
from app.config import get_settings
from app.main import app  # noqa: F401

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
