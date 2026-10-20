# L4 / L5 / L6 → live GCP

## Already live

| | |
| --- | --- |
| Service | https://finance-ops-301858971164.us-central1.run.app |
| Project | `gen-lang-client-0611250410` |
| Method | Cloud Run **Connect repository** → Cloud Build → deploy |
| Confirm | `/health`, `/docs`, `POST /v1/bootstrap`, `POST /v1/aging` |

No service-account JSON in chat is required for this path.

## Script path (optional / CI)

One script for agent or workstation deploy (needs ADC or `GCP_SA_KEY_JSON`):

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export FINANCE_OPS_REGION=us-central1   # optional
bash scripts/go_live_gcp.sh
```

| Step | L# | Action |
| --- | --- | --- |
| Enable APIs | — | Run, AR, AI Platform, BQ, GCS, … |
| Terraform | L3/L6 | Dataset, Pub/Sub, AR, SA, embeddings bucket |
| Cloud Build | L6 | Build/push `finance-ops` image |
| Cloud Run | L6 | Deploy with public `/health` |
| Env | L4/L5 | `USE_VERTEX_VECTORS=true`, `GRAPH_BACKEND=sqlite` |
| GCS upload | L4 | Policy vector catalog → embeddings bucket |
| Smoke | — | bootstrap, aging, search, status |

## Env vars on Cloud Run

Set under **Edit & deploy new revision → Variables**:

```text
FINANCE_OPS_DATA_MODE=warehouse
FINANCE_OPS_USE_VERTEX_VECTORS=true
FINANCE_OPS_GRAPH_BACKEND=sqlite
GOOGLE_CLOUD_PROJECT=gen-lang-client-0611250410
```

## Parking lot after go-live

- Enable BigQuery API + load tables for true L3 BQ reads.
- Create Matching Engine index; set `FINANCE_OPS_VECTOR_INDEX_ENDPOINT`.
- Point `NEO4J_URI` for managed Neo4j (`FINANCE_OPS_GRAPH_BACKEND=neo4j`).

See [master-plan-status.md](master-plan-status.md).
