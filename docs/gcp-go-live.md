# L4 / L5 / L6 → live GCP

One script turns the merged ladder into a running Cloud Run service.

## Prerequisites

1. GCP project with **billing**
2. Auth — either:
   - `gcloud auth login` + `gcloud auth application-default login`, or
   - Service account JSON → `GCP_SA_KEY_JSON=/path/to/key.json`
3. Tools: `gcloud`, `terraform`, Python deps (`pip install -r requirements.txt`)

## Run

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export FINANCE_OPS_REGION=us-central1   # optional
# export GCP_SA_KEY_JSON=/path/to/sa.json

bash scripts/go_live_gcp.sh
```

What it does:

| Step | L# | Action |
| --- | --- | --- |
| Enable APIs | — | Run, AR, AI Platform, BQ, GCS, … |
| Terraform | L3/L6 | Dataset, Pub/Sub, AR, SA, embeddings bucket |
| Cloud Build | L6 | Build/push `finance-ops` image |
| Cloud Run | L6 | Deploy with public `/health` |
| Env | L4/L5 | `USE_VERTEX_VECTORS=true`, `GRAPH_BACKEND=sqlite` |
| GCS upload | L4 | Policy vector catalog → embeddings bucket |
| Smoke | — | `POST /v1/bootstrap`, aging, search, status |

## After go-live

```bash
URI=$(terraform -chdir=infra/terraform output -raw cloud_run_uri)
curl -s "$URI/health"
curl -s -X POST "$URI/v1/aging" -H 'Content-Type: application/json' \
  -d '{"customer_id":"CUST-ACME"}'
```

**Matching Engine endpoint (optional follow-up):** create/deploy a Vector Search index from `gs://…-finance-ops-embeddings/vectors/`, then:

```bash
gcloud run services update finance-ops --region=$FINANCE_OPS_REGION \
  --update-env-vars=FINANCE_OPS_VECTOR_INDEX_ENDPOINT=ENDPOINT_RESOURCE_NAME
```

Until then the service uses Vertex embeddings (when permitted) + in-container ME simulator — still a live L4 path.

**Neo4j:** set `NEO4J_URI` / user / password on the Cloud Run service (Aura or GCE) and `FINANCE_OPS_GRAPH_BACKEND=neo4j`. Default live graph is **sqlite** inside the revision (synced on `/v1/bootstrap`).
