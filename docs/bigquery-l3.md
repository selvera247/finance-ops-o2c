# BigQuery L3 — invoice / payment tools

Agent tools keep the same contracts. `data_plane.repository` switches on
`FINANCE_OPS_DATA_MODE=bigquery` and calls `bq_adapter`, which **falls back to
DuckDB** when ADC/project/client are missing (safe for demos).

## Enable

```bash
# finance_ops/.env
FINANCE_OPS_DATA_MODE=bigquery
GOOGLE_CLOUD_PROJECT=your-gcp-project
FINANCE_OPS_BQ_DATASET=finance_ops
# ADC: gcloud auth application-default login
```

```bash
pip install google-cloud-bigquery
# Terraform dataset (optional)
# cd infra/terraform && terraform apply -var=project_id=...
# Apply DDL (replace PROJECT/DATASET)
# bq query --use_legacy_sql=false < data_plane/warehouse/bq_schema.sql

PYTHONPATH=. python scripts/load_bigquery_demo.py --dry-run
PYTHONPATH=. python scripts/load_bigquery_demo.py
```

## Verify

In ADK: `bigquery_status` → `bigquery.ok=true`, `active_source=bigquery`.  
Invoice/payment tools then read BQ; without credentials they still answer from DuckDB and set `needs_review` on status.
