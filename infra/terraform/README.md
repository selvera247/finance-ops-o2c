# Terraform skeleton (GCP Data → AI)

Provisions the cloud spine for this portfolio:

- BigQuery dataset `finance_ops`
- Pub/Sub topic/subscription `finance-ops-events`
- Artifact Registry repo for agent images

## Usage

```bash
cd infra/terraform
terraform init
terraform plan -var="project_id=YOUR_GCP_PROJECT"
terraform apply -var="project_id=YOUR_GCP_PROJECT"
```

Then set:

```bash
export GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT
export FINANCE_OPS_DATA_MODE=bigquery
export FINANCE_OPS_BQ_DATASET=finance_ops
```

Local DuckDB remains the default for demos without GCP (`FINANCE_OPS_DATA_MODE=warehouse`).
