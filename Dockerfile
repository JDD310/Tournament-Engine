# syntax=docker/dockerfile:1

# Tournament Engine: one image with the FastAPI backend and the built React app.
#
#   docker build -t tournament-engine .
#   docker run -p 8080:8080 --env-file .env tournament-engine
#
# See docs/deploy.md for Cloud Run.

# ---- Stage 1: build the frontend -------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend
# Install dependencies first so this layer is cached until the lockfile changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime -----------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Cloud Run sets PORT; 8080 is its default and the local default here.
    PORT=8080 \
    # Makes the app serve the built frontend (backend/app/spa.py).
    FRONTEND_DIST=/app/static

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt \
    && useradd --system --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY --chmod=755 backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY --from=frontend /frontend/dist ./static

# Everything above is owned by root and read-only to the app user.
USER app

EXPOSE 8080

# Used by `docker run`/compose. Cloud Run ignores HEALTHCHECK; see docs/deploy.md.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8080'), timeout=4)"

ENTRYPOINT ["docker-entrypoint.sh"]
