# Container image for Google Cloud Run (or any Docker host).
# Plotly Dash app exposing `server = app.server` in app.py; dependencies installed with uv from uv.lock.
FROM python:3.13-slim

# uv binary, pinned version (official image)
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install the exact locked dependencies first (cached layer), without dev tools (pytest)
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code and assets
COPY . .

# Cloud Run provides $PORT (8080 by default). One worker with several threads; the app keeps no server-side state.
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 120 app:server
