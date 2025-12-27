
gcloud config set project mailbox-stats-dev
gcloud components update
gcloud secrets create gmail-token-json --data-file=token.json
gcloud run jobs describe mailbox-stats \
  --region us-central1 \
  --format="value(spec.template.spec.serviceAccountName)"

gcloud auth configure-docker us-central1-docker.pkg.dev
IMAGE="us-central1-docker.pkg.dev/mailbox-stats-dev/mailbox-stats/mailbox-stats:latest"\ndocker build -t "$IMAGE" .
docker push "$IMAGE"

gcloud run jobs create mailbox-stats \
  --image "us-central1-docker.pkg.dev/mailbox-stats-dev/mailbox-stats/mailbox-stats:latest" \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 3600 \
  --max-retries 0

gcloud iam service-accounts create mailbox-stats-job \
  --display-name="Mailbox Stats Cloud Run Job"

gcloud run jobs update mailbox-stats \
  --region us-central1 \
  --service-account mailbox-stats-job@mailbox-stats-dev.iam.gserviceaccount.com

gcloud iam service-accounts list \
  --filter="mailbox-stats-job"

gcloud run jobs update mailbox-stats \
  --region us-central1 \
  --service-account mailbox-stats-job@mailbox-stats-dev.iam.gserviceaccount.com
gcloud run jobs describe mailbox-stats \
  --region us-central1 \
  --format="value(spec.template.spec.serviceAccountName)"
gcloud run jobs describe mailbox-stats \
  --region us-central1 \
  --format="yaml" | grep -n "serviceAccount"

gcloud projects add-iam-policy-binding mailbox-stats-dev \
  --member="serviceAccount:mailbox-stats-job@mailbox-stats-dev.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects get-iam-policy mailbox-stats-dev \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/secretmanager.secretAccessor AND bindings.members:mailbox-stats-job" \
  --format="table(bindings.role, bindings.members)"

gcloud run jobs update mailbox-stats \
  --region us-central1 \
  --set-secrets "GMAIL_TOKEN_JSON=gmail-token-json:latest"
gcloud run jobs execute mailbox-stats --region us-central1
gcloud logging read \
  --project mailbox-stats-dev \
  --limit 100 \
  --format="value(textPayload)"

