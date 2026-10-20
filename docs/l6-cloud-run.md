# L6 — Cloud Run deploy

## What shipped

- `Dockerfile` + `finance_ops/serving.py` (FastAPI `/health`, bootstrap, aging, RAG, HITL)
- `infra/terraform` — Artifact Registry, SA IAM, **Cloud Run v2**, embeddings bucket, BQ, Pub/Sub
- `scripts/deploy_cloud_run.sh`
- `docker-compose.yml` for local API + Neo4j

## Local API smoke

```bash
pip install -r requirements.txt -r requirements-cloud.txt
PYTHONPATH=. uvicorn finance_ops.serving:app --port 8080
curl -s localhost:8080/health
curl -s -X POST localhost:8080/v1/bootstrap | head
```

## Deploy

```bash
export GOOGLE_CLOUD_PROJECT=your-project
# one-time: enable run, artifactregistry, aiplatform, bigquery APIs
bash scripts/deploy_cloud_run.sh
# opens Cloud Run URL from terraform output
curl -s "$(terraform -chdir=infra/terraform output -raw cloud_run_uri)/health"
```

## ADK web vs API

- **Local demos:** `adk web` (full multi-agent UI)
- **Cloud Run:** HTTP API above (portable, health-checked). Wire ADK Agent Engine later on the same image if needed.
