# Cloud Run Deployment

Quick commands to deploy Biome to Google Cloud Run.

## Setup Cloud SQL

```bash
gcloud sql instances create biome-db --database-version=POSTGRES_15 --tier=db-f1-micro --region=us-central1
gcloud sql databases create biome_coaching --instance=biome-db

# Apply schema via proxy
cloud_sql_proxy -instances=PROJECT:REGION:biome-db=tcp:5432 &
psql "postgresql://postgres:PASSWORD@localhost:5432/biome_coaching" -f schema.sql
```

## Deploy Backend

```bash
gcloud run deploy biome-backend \
  --source . \
  --region=us-central1 \
  --memory=4Gi \
  --timeout=300s \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_API_KEY=your-key,DATABASE_URL=postgresql://...,PORT=8080" \
  --add-cloudsql-instances=PROJECT:REGION:biome-db
```

## Deploy Frontend (Optional: +0.4 bonus points)

```bash
gcloud run deploy biome-frontend \
  --source . \
  --region=us-central1 \
  --set-env-vars="REACT_APP_API_URL=https://biome-backend-xxx.run.app"
```

## Verify

```bash
# Get URLs
gcloud run services list --region=us-central1

# Test
curl https://your-backend-url.run.app/health
```

---

**Tip**: Deploy frontend separately for +0.4 bonus points (multiple Cloud Run services).
