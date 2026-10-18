#!/usr/bin/env bash
# Build with Cloud Build and deploy to Cloud Run. Needs deploy/gcp_setup.sh to have run, plus:
#   FALKORDB_HOST=... FALKORDB_PORT=... [FALKORDB_USERNAME=default] [FALKORDB_SSL=true] bash deploy/gcp_deploy.sh
# The service is private (IAM-authenticated) because the app has no login of its own. To reach it:
#   gcloud run services proxy ripple --region us-central1      # http://localhost:8080
set -euo pipefail
P=${GCP_PROJECT:-$(gcloud config get-value project)}
R=${GCP_REGION:-us-central1}
IMG=$R-docker.pkg.dev/$P/ripple/ripple:$(git rev-parse --short HEAD)

gcloud builds submit --tag "$IMG" --project "$P" .

# one instance, CPU always on: incident runs are background threads that outlive the request
gcloud run deploy ripple --image "$IMG" --region "$R" --project "$P" \
  --service-account "ripple-run@$P.iam.gserviceaccount.com" \
  --port 8000 --memory 2Gi --cpu 2 --no-cpu-throttling --min-instances 1 --max-instances 1 \
  --timeout 3600 --concurrency 40 --no-allow-unauthenticated \
  --set-env-vars "RIPPLE_DB_MODE=remote,FALKORDB_HOST=${FALKORDB_HOST:?},FALKORDB_PORT=${FALKORDB_PORT:?},FALKORDB_USERNAME=${FALKORDB_USERNAME:-default},FALKORDB_SSL=${FALKORDB_SSL:-true},RIPPLE_LLM_PROVIDER=vertex,VERTEX_PROJECT_ID=$P,VERTEX_REGION=${VERTEX_REGION:-global},VERTEX_MODEL=${VERTEX_MODEL:-gemini-3.1-pro-preview},RIPPLE_TENANTS_DIR=/app/var/tenants" \
  --set-secrets "FALKORDB_PASSWORD=ripple-falkordb-password:latest,OPENROUTER_API_KEY=ripple-openrouter-key:latest,RIPPLE_WEBHOOK_SECRET=ripple-webhook-secret:latest"
gcloud run services describe ripple --region "$R" --project "$P" --format='value(status.url)'
