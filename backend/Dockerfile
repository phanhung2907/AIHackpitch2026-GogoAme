FROM python:3.12-slim AS builder

WORKDIR /build/backend
RUN pip install --no-cache-dir uv==0.10.0

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runner

RUN groupadd -g 1001 appgroup && useradd -r -u 1001 -g appgroup appuser
WORKDIR /app/backend

COPY --from=builder /build/backend/.venv /app/backend/.venv
COPY contracts /app/contracts
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/alembic /app/backend/alembic
COPY backend/app /app/backend/app

ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1" \
    PORT="8000"

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os, urllib.request; p = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health/live', timeout=2)" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

