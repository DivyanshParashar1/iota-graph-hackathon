#!/usr/bin/env bash
# One-time GCP setup for Ripple on Cloud Run. Run it yourself: it grants IAM roles and stores secrets.
#   FALKORDB_PASSWORD=... OPENROUTER_API_KEY=... bash deploy/gcp_setup.sh
# Secret values come from the environment, never from files in the repo.
set -euo pipefail
P=${GCP_PROJECT:-$(gcloud config get-value project)}
R=${GCP_REGION:-us-central1}
SA=ripple-run@$P.iam.gserviceaccount.com

gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com \
  aiplatform.googleapis.com cloudbuild.googleapis.com --project "$P"

gcloud iam service-accounts describe "$SA" --project "$P" >/dev/null 2>&1 ||
  gcloud iam service-accounts create ripple-run --display-name="Ripple Cloud Run" --project "$P"
for role in roles/aiplatform.user roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:$SA" --role="$role" --condition=None --quiet >/dev/null
done

gcloud artifacts repositories describe ripple --location "$R" --project "$P" >/dev/null 2>&1 ||
  gcloud artifacts repositories create ripple --repository-format=docker --location "$R" --project "$P"

# only the secrets the deployment needs: FalkorDB password, OpenRouter key (Jev), webhook secret
put() {  # name value
  gcloud secrets describe "$1" --project "$P" >/dev/null 2>&1 || gcloud secrets create "$1" --replication-policy=automatic --project "$P"
  printf %s "$2" | gcloud secrets versions add "$1" --data-file=- --project "$P" >/dev/null
}
put ripple-falkordb-password "${FALKORDB_PASSWORD:?set FALKORDB_PASSWORD}"
put ripple-openrouter-key "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
put ripple-webhook-secret "${RIPPLE_WEBHOOK_SECRET:-$(openssl rand -hex 24)}"
echo "setup done: project=$P region=$R"
