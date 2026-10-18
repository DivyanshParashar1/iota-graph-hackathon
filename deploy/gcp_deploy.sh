#!/usr/bin/env bash
# Build with Cloud Build and deploy to Cloud Run. Needs deploy/gcp_setup.sh to have run, plus:
#   FALKORDB_HOST=... FALKORDB_PORT=... FALKORDB_USERNAME=... [FALKORDB_SSL=true] bash deploy/gcp_deploy.sh
# Pass the FalkorDB values on the command line, not from a sourced .env: that file points at the local database.
# A new service is private (IAM-authenticated); access on an existing one is left as it is. Private access:
#   gcloud run services proxy ripple --region asia-south1      # http://localhost:8080
set -euo pipefail
P=${GCP_PROJECT:-$(gcloud config get-value project)}
R=${GCP_REGION:-us-central1}
case "${FALKORDB_HOST:-}" in
  ""|localhost|127.*|0.0.0.0) echo "FALKORDB_HOST=${FALKORDB_HOST:-<unset>} is not reachable from Cloud Run; pass the FalkorDB Cloud host" >&2; exit 1;;
esac
IMG=$R-docker.pkg.dev/$P/ripple/ripple:$(git rev-parse --short HEAD)

gcloud builds submit --tag "$IMG" --project "$P" .

# one instance, CPU always on: incident runs are background threads that outlive the request
gcloud run deploy ripple --image "$IMG" --region "$R" --project "$P" \
  --service-account "ripple-run@$P.iam.gserviceaccount.com" \
  --port 8000 --memory 2Gi --cpu 2 --no-cpu-throttling --min-instances 1 --max-instances 1 \
  --timeout 3600 --concurrency 40 \
  --set-env-vars "RIPPLE_DB_MODE=remote,FALKORDB_HOST=${FALKORDB_HOST:?},FALKORDB_PORT=${FALKORDB_PORT:?},FALKORDB_USERNAME=${FALKORDB_USERNAME:?},FALKORDB_SSL=${FALKORDB_SSL:-false},RIPPLE_LLM_PROVIDER=vertex,VERTEX_PROJECT_ID=$P,VERTEX_REGION=${VERTEX_REGION:-global},VERTEX_MODEL=${VERTEX_MODEL:-gemini-3.1-pro-preview},RIPPLE_TENANTS_DIR=/app/var/tenants" \
  --set-secrets "FALKORDB_PASSWORD=ripple-falkordb-password:latest,OPENROUTER_API_KEY=ripple-openrouter-key:latest,RIPPLE_WEBHOOK_SECRET=ripple-webhook-secret:latest"
gcloud run services describe ripple --region "$R" --project "$P" --format='value(status.url)'
