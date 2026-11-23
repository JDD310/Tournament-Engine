#!/usr/bin/env bash
# Build, push, migrate and deploy Tournament Engine to Cloud Run.
#
# Does steps 4, 6 and 7 of docs/deploy.md. The one-time setup (project, APIs,
# Artifact Registry repo, secrets, service account) must already be done.
#
# By default this only PRINTS the commands. Pass --run to execute them.
# Nothing account-specific is stored here: everything comes from env vars.
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: PROJECT_ID=... REGION=... scripts/deploy-cloud-run.sh [--run]

Without --run the commands are printed, not executed.

Required:
  PROJECT_ID        Google Cloud project ID
  REGION            Cloud Run / Artifact Registry region, e.g. us-east1

Optional (defaults in brackets):
  REPO              Artifact Registry repository [tournament-engine]
  SERVICE           Cloud Run service name [tournament-engine]
  JOB               Cloud Run migration job name [tournament-engine-migrate]
  SA                Runtime service account
                    [tournament-engine-run@$PROJECT_ID.iam.gserviceaccount.com]
  TAG               Image tag [git short SHA]
  APP_SECRET        Secret with the pooled Neon URL [database-url]
  MIGRATE_SECRET    Secret with the direct Neon URL [database-url-direct]
  MAX_INSTANCES     [2]
USAGE
}

EXECUTE=0
case "${1:-}" in
    --run) EXECUTE=1 ;;
    -h | --help) usage; exit 0 ;;
    "") ;;
    *) usage >&2; exit 2 ;;
esac

: "${PROJECT_ID:?Set PROJECT_ID (see --help)}"
: "${REGION:?Set REGION (see --help)}"
REPO="${REPO:-tournament-engine}"
SERVICE="${SERVICE:-tournament-engine}"
JOB="${JOB:-tournament-engine-migrate}"
SA="${SA:-tournament-engine-run@$PROJECT_ID.iam.gserviceaccount.com}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
APP_SECRET="${APP_SECRET:-database-url}"
MIGRATE_SECRET="${MIGRATE_SECRET:-database-url-direct}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/app:$TAG"

cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain)" ]; then
    echo "warning: the working tree has uncommitted changes; tag $TAG won't match the image contents" >&2
fi

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    if [ "$EXECUTE" = 1 ]; then
        "$@"
    fi
}

# Step 4: build for Cloud Run's platform (needed on Apple Silicon) and push.
run docker build --platform linux/amd64 -t "$IMAGE" .
run docker push "$IMAGE"

# Step 6: migrate once, with the direct Neon URL, before the new revision.
run gcloud run jobs deploy "$JOB" \
    --project="$PROJECT_ID" --region="$REGION" \
    --image="$IMAGE" \
    --service-account="$SA" \
    --set-secrets="DATABASE_URL=$MIGRATE_SECRET:latest" \
    --args="python,-m,app.migrate" \
    --tasks=1 --max-retries=0 --task-timeout=300s \
    --cpu=1 --memory=512Mi
run gcloud run jobs execute "$JOB" --project="$PROJECT_ID" --region="$REGION" --wait

# Step 7: deploy with free-tier settings and the pooled Neon URL.
run gcloud run deploy "$SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" \
    --image="$IMAGE" \
    --service-account="$SA" \
    --set-secrets="DATABASE_URL=$APP_SECRET:latest" \
    --allow-unauthenticated \
    --port=8080 \
    --min-instances=0 --max-instances="$MAX_INSTANCES" \
    --cpu=1 --memory=512Mi \
    --concurrency=80 --timeout=60s \
    --cpu-throttling

if [ "$EXECUTE" = 1 ]; then
    URL=$(gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')
    echo "Deployed: $URL"
    echo "Check:    curl -i $URL/api/health   (then follow step 8 of docs/deploy.md)"
else
    echo
    echo "Printed only. Re-run with --run to execute."
fi
