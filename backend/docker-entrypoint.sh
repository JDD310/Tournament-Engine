#!/bin/sh
# Container entrypoint.
#
# With no arguments it starts the web server on $PORT. If MIGRATE_ON_START is
# true it first runs the migrations (python -m app.migrate); that is meant for
# local `docker run` only. On Cloud Run, run migrations once per deploy as a
# Cloud Run job instead (docs/deploy.md): Alembic takes no lock, so instances
# starting at the same time would race on the schema.
#
# With arguments it runs them instead, e.g. `python -m app.migrate` for the
# migration job.
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
    echo "DATABASE_URL is not set. Pass it with --env-file .env or -e DATABASE_URL=..." >&2
    exit 1
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

case "${MIGRATE_ON_START:-false}" in
    true | 1 | yes)
        echo "MIGRATE_ON_START is set: running migrations"
        python -m app.migrate
        ;;
esac

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --no-server-header
