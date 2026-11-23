# Deploying to Google Cloud Run

This runbook takes the app from a clean checkout to a public Cloud Run URL backed by a Neon Postgres database. You run every command yourself, with your own Google Cloud account; nothing in the repo has credentials or account details.

The pieces:

| Piece | What it is |
|---|---|
| Docker image | `Dockerfile` at the repo root: builds the React app, then a slim Python 3.13 image that serves the API and the built frontend on `$PORT` |
| Artifact Registry | Stores the image |
| Secret Manager | Holds the Neon connection strings, so they never appear in the repo, the image, or the service config |
| Cloud Run job `tournament-engine-migrate` | Runs `python -m app.migrate` once per deploy |
| Cloud Run service `tournament-engine` | The public app |

`scripts/deploy-cloud-run.sh` automates the repeatable part (steps 4, 6 and 7) once the one-time setup is done. See [Deploy script](#deploy-script).

## Before you start

- A Google account with billing enabled. Cloud Run requires a billing account even when usage stays inside the free tier. Set a budget alert (see [Free tier](#free-tier-what-is-free-and-what-can-cost-money)).
- A Neon project with a database. In the Neon console, **Connect** shows two connection strings for the same database:
  - **Pooled** (host contains `-pooler`, for example `ep-cool-name-123456-pooler.us-east-2.aws.neon.tech`). Goes through Neon's PgBouncer. Use it for the **app**.
  - **Direct** (same host without `-pooler`). Use it for **migrations**.
- Docker Desktop running locally.

Set these once in your shell. Pick a Cloud Run region close to your Neon region (for example Neon `aws-us-east-1` / `aws-us-east-2` with `us-east4` or `us-east1`), since every database query crosses that link.

```sh
export PROJECT_ID=your-project-id          # globally unique, e.g. tournament-engine-1234
export REGION=us-east1                     # Cloud Run + Artifact Registry region
export REPO=tournament-engine              # Artifact Registry repository
export SERVICE=tournament-engine           # Cloud Run service name
export SA_NAME=tournament-engine-run       # runtime service account
export SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/app"
```

## 1. Install and authenticate gcloud

Install the Google Cloud CLI: https://cloud.google.com/sdk/docs/install (on macOS with Homebrew: `brew install --cask google-cloud-sdk`). Then:

```sh
gcloud auth login
gcloud auth configure-docker "$REGION-docker.pkg.dev"   # lets `docker push` use your gcloud login
```

## 2. Create or select a project and enable the APIs

Create a new project (skip if you already have one), link billing, and make it the default:

```sh
gcloud projects create "$PROJECT_ID"
gcloud billing accounts list                                   # find your billing account ID
gcloud billing projects link "$PROJECT_ID" --billing-account=XXXXXX-XXXXXX-XXXXXX
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
```

Enable Cloud Run, Artifact Registry and Secret Manager:

```sh
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 3. Create the Artifact Registry repository

```sh
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Tournament Engine images"
```

Keep only recent images so storage stays under the free 0.5 GB. Save this as `cleanup-policy.json` (anywhere outside the repo is fine):

```json
[
  {"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}},
  {"name": "delete-old", "action": {"type": "Delete"}, "condition": {"olderThan": "7d"}}
]
```

```sh
gcloud artifacts repositories set-cleanup-policies "$REPO" \
  --location="$REGION" --policy=cleanup-policy.json --no-dry-run
```

Keep policies win over delete policies, so the three newest images always stay.

## 4. Build and push the image

Cloud Run runs `linux/amd64`. On an Apple Silicon Mac, `docker build` makes an arm64 image by default, which Cloud Run rejects, so always pass `--platform linux/amd64`:

```sh
export TAG=$(git rev-parse --short HEAD)
docker build --platform linux/amd64 -t "$IMAGE:$TAG" .
docker push "$IMAGE:$TAG"
```

Use a tag per commit rather than only `latest`, so a deploy always names an exact image and a rollback is just redeploying an older tag.

## 5. Store the Neon connection strings in Secret Manager

Two secrets: the pooled URL for the app and the direct URL for migrations. Make sure each ends in `?sslmode=require` (Neon includes it; keep it). `read -s` keeps the value out of your shell history and off the screen:

```sh
read -rs POOLED_URL   # paste the Neon *pooled* connection string, then Enter
printf '%s' "$POOLED_URL" | gcloud secrets create database-url --data-file=-

read -rs DIRECT_URL   # paste the Neon *direct* connection string, then Enter
printf '%s' "$DIRECT_URL" | gcloud secrets create database-url-direct --data-file=-

unset POOLED_URL DIRECT_URL
```

Create a dedicated runtime service account and let it read only these two secrets (rather than using the default Compute Engine account, which has broad project access):

```sh
gcloud iam service-accounts create "$SA_NAME" --display-name="Tournament Engine (Cloud Run)"

for secret in database-url database-url-direct; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
done
```

To rotate a password later, add a new version (`printf '%s' "$NEW_URL" | gcloud secrets versions add database-url --data-file=-`), redeploy so new instances pick it up, then destroy the old version (`gcloud secrets versions destroy <n> --secret=database-url`).

## 6. Run the migrations

Migrations run **once per deploy, before the new revision takes traffic**, as a Cloud Run job that uses the same image. They are deliberately **not** in the service's start command:

- Cloud Run starts an instance on every cold start and may start several at once when traffic arrives. Migrating in the start command would run Alembic on each of them.
- `python -m app.migrate` takes no lock. On Postgres, two instances upgrading at the same time both try the same DDL: one blocks on the other's locks and then fails ("relation already exists", or a duplicate key on `alembic_version`), so that instance crashes on start. With `max-instances` above 1 that is a real race, not a theory.
- It would also add a Neon round trip (and possibly a Neon wake-up) to every cold start, and an old revision still serving traffic would briefly run against a schema it doesn't know about without any ordering guarantee.

A job gives one run at a known moment, and the deploy only proceeds if it succeeds. (`MIGRATE_ON_START=true` in `.env.example` exists only for the one-container `docker run` case locally; don't set it on Cloud Run.)

Create or update the job to point at the image you just pushed, then run it and wait:

```sh
gcloud run jobs deploy tournament-engine-migrate \
  --image="$IMAGE:$TAG" \
  --region="$REGION" \
  --service-account="$SA" \
  --set-secrets=DATABASE_URL=database-url-direct:latest \
  --args="python,-m,app.migrate" \
  --tasks=1 --max-retries=0 --task-timeout=300s \
  --cpu=1 --memory=512Mi

gcloud run jobs execute tournament-engine-migrate --region="$REGION" --wait
```

The job uses the **direct** Neon URL: PgBouncer in transaction mode (the pooled endpoint) can hand consecutive statements to different server connections, which breaks session state, and Neon recommends direct connections for schema changes. If it was asleep, Neon wakes the compute on connect; that takes a few seconds and is well inside the 300 s task timeout.

If the job fails, read its logs (`gcloud run jobs executions list --job=tournament-engine-migrate --region="$REGION"`, then follow the log link) and **don't** deploy the service.

**Alternative without a job:** run the same image locally against the direct URL. This is fine for a one-person project; the job is better once deploys are automated (TE-16).

```sh
read -rs DATABASE_URL && export DATABASE_URL      # the direct URL
docker run --rm -e DATABASE_URL tournament-engine python -m app.migrate
unset DATABASE_URL
```

## 7. Deploy the service

```sh
gcloud run deploy "$SERVICE" \
  --image="$IMAGE:$TAG" \
  --region="$REGION" \
  --service-account="$SA" \
  --set-secrets=DATABASE_URL=database-url:latest \
  --allow-unauthenticated \
  --port=8080 \
  --min-instances=0 \
  --max-instances=2 \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=80 \
  --timeout=60s \
  --cpu-throttling
```

What the settings do:

| Flag | Why |
|---|---|
| `--allow-unauthenticated` | The tournament pages are public. Organizer actions are protected by the admin token, not by Cloud IAM. |
| `--set-secrets=DATABASE_URL=database-url:latest` | Injects the **pooled** Neon URL as the `DATABASE_URL` env var. Only the secret's name is in the service config. |
| `--min-instances=0` | Scales to zero when idle, so an idle app costs nothing. The trade-off is a cold start (a couple of seconds) on the first request after idling. |
| `--max-instances=2` | Caps cost and the number of Neon connections if something hammers the URL. |
| `--cpu=1 --memory=512Mi` | Small and enough for this app. |
| `--cpu-throttling` | Request-based billing: you're billed only while a request is being handled. This is the default; it's spelled out because `--no-cpu-throttling` would bill for the whole instance lifetime. |
| `--timeout=60s` | Plenty for a request even when Neon has to wake up first. |

### Neon cold starts and Cloud Run startup

Both sides scale to zero, so the first visit after a quiet period can wake both:

- The container starts without touching the database: the SQLAlchemy engine connects lazily, and `/api/health` doesn't query it (see TE-63). So Neon being asleep can't make the container fail Cloud Run's startup check. The default startup probe (a TCP check on the port) is enough; startup takes about a second or two.
- The first request that needs the database waits for Neon to resume, typically under a few seconds. That's well inside `--timeout=60s`. `pool_pre_ping` in `app/db.py` discards connections Neon closed while suspended, so a stale pooled connection doesn't turn into an error.
- Neon's free plan suspends compute after 5 minutes idle. Don't add a keep-alive ping to avoid it: that burns both Neon compute hours and Cloud Run free requests for little benefit.

Optional: to make Cloud Run use the app's own health endpoint, add an HTTP startup probe on `/api/health`, port 8080 (Console: the service, **Edit & deploy new revision**, **Container**, **Health checks**). Keep in mind it only proves the process is up, not that the database is reachable.

## 8. Verify

```sh
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')
echo "$URL"

curl -i "$URL/api/health"
# HTTP/2 200 ... referrer-policy: same-origin ... {"status":"ok"}
```

`/api/health` only shows the app is running. To check the **Neon connection**, create a tournament (this writes to the database) and read it back:

```sh
curl -s -X POST "$URL/api/tournaments" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Deploy check","game":"Test","format":"single_elimination"}'
# {"id":"<id>", ... "public_path":"/t/<id>", ...}

curl -s "$URL/api/tournaments/<id>/public"
```

Then in a browser:

1. Open `$URL`. The create-tournament page loads.
2. Create a tournament and follow the organizer link. Reload the page on `/t/<id>/manage`: it should load again (deep links are served `index.html`), not show a 404.
3. Open `$URL/t/<id>` on a phone or a private window.
4. Open `$URL/some/missing/page`: the app's own not-found page appears.

If the create request fails with a 500, check the logs: `gcloud run services logs read "$SERVICE" --region="$REGION" --limit=50`. The usual causes are a wrong secret value, a missing `sslmode=require`, or migrations not having run (step 6).

### Rolling back

```sh
gcloud run revisions list --service="$SERVICE" --region="$REGION"
gcloud run services update-traffic "$SERVICE" --region="$REGION" --to-revisions=<previous-revision>=100
```

Migrations aren't rolled back automatically. Only roll back the app across a migration if the older code still works with the newer schema.

## Free tier: what is free and what can cost money

Free-tier amounts change; check https://cloud.google.com/free and https://neon.tech/pricing before relying on them. At the time of writing:

**Stays free with the settings above**

- **Cloud Run (service and job), request-based billing:** the monthly free allowance (about 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests) is far more than a demo app uses. With `--min-instances=0` and `--cpu-throttling`, an idle app costs nothing. A migration job run is a few seconds of 1 vCPU.
- **Artifact Registry:** 0.5 GB of storage free. The image is about 70 MB compressed, so the cleanup policy (3 newest images) keeps it well under. Pulling the image into Cloud Run in the same region is free.
- **Secret Manager:** 6 active secret versions and 10,000 access operations free per month. Two secrets with one version each, read on instance start, is well within it.
- **Neon free plan:** one project, 0.5 GB storage, a monthly allowance of compute hours with scale-to-zero.
- **Cloud Logging:** the first 50 GiB of logs per month.

**Can cost money**

- `--min-instances` of 1 or more: an instance stays up all month and is billed for its idle time too (from a few dollars to tens of dollars a month, depending on size).
- `--no-cpu-throttling` (instance-based billing): billed for the instance's whole lifetime, not just requests.
- A high `--max-instances`, or larger `--cpu` / `--memory`, under heavy or abusive traffic.
- Keeping many images in Artifact Registry (beyond 0.5 GB), or pushing to a repo in a different region from the service (cross-region transfer).
- `gcloud run deploy --source .` or `gcloud builds submit`: these build with Cloud Build, which has its own quota. This runbook builds locally to avoid that.
- Internet egress beyond the free amount (1 GiB per month from North America).
- More secret versions than the free 6 (destroy old versions after rotating).
- Going over Neon's free limits (Neon suspends the compute rather than billing you on the free plan).

Set a budget alert so a mistake is noticed early: Console, **Billing**, **Budgets & alerts**, create a budget of, say, $1 with email alerts. A budget alerts; it doesn't stop spending.

## Deploy script

After the one-time setup (steps 1 to 3 and 5), `scripts/deploy-cloud-run.sh` does steps 4, 6 and 7. It reads everything from environment variables, has no account details in it, and by default **only prints** the commands:

```sh
PROJECT_ID=your-project-id REGION=us-east1 scripts/deploy-cloud-run.sh          # print the commands
PROJECT_ID=your-project-id REGION=us-east1 scripts/deploy-cloud-run.sh --run    # run them
```

Run `scripts/deploy-cloud-run.sh --help` for the optional variables (service name, repository, tag, secret names, service account).

## Tearing down

```sh
gcloud run services delete "$SERVICE" --region="$REGION"
gcloud run jobs delete tournament-engine-migrate --region="$REGION"
gcloud artifacts repositories delete "$REPO" --location="$REGION"
gcloud secrets delete database-url
gcloud secrets delete database-url-direct
# or delete the whole project: gcloud projects delete "$PROJECT_ID"
```
