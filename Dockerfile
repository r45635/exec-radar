# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ---------------------------------------------------------------------------
# Builder stage – install dependencies
# ---------------------------------------------------------------------------
FROM base AS builder

COPY pyproject.toml ./
COPY packages/schemas      packages/schemas
COPY packages/normalizers  packages/normalizers
COPY packages/collectors   packages/collectors
COPY packages/rankers      packages/rankers
COPY packages/notifications packages/notifications
COPY apps/api              apps/api

# Install packages in editable / flat mode so all imports resolve
RUN pip install --upgrade pip \
 && pip install pydantic>=2.7.0 pydantic-settings>=2.3.0 \
 && pip install -e packages/schemas \
 && pip install -e packages/normalizers \
 && pip install -e packages/collectors \
 && pip install -e packages/rankers \
 && pip install -e packages/notifications \
 && pip install fastapi>=0.111.0 "uvicorn[standard]>=0.29.0" python-dotenv>=1.0.0 httpx>=0.27.0

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM base AS runtime

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

WORKDIR /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
