terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "dataset_id" {
  type    = string
  default = "finance_ops"
}

variable "service_name" {
  type    = string
  default = "finance-ops"
}

variable "image" {
  type        = string
  description = "Container image in Artifact Registry, e.g. REGION-docker.pkg.dev/PROJECT/finance-agents/finance-ops:latest"
  default     = ""
}

variable "invoker_members" {
  type        = list(string)
  description = "Who can invoke Cloud Run (use allUsers only for public demos)"
  default     = []
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_bigquery_dataset" "finance_ops" {
  dataset_id = var.dataset_id
  location   = var.region
}

# Table DDL is applied via data_plane/warehouse/bq_schema.sql (bq CLI) after dataset create.

resource "google_pubsub_topic" "finance_events" {
  name = "finance-ops-events"
}

resource "google_pubsub_subscription" "finance_events_sub" {
  name  = "finance-ops-events-sub"
  topic = google_pubsub_topic.finance_events.name
}

resource "google_artifact_registry_repository" "agents" {
  location      = var.region
  repository_id = "finance-agents"
  format        = "DOCKER"
}

resource "google_service_account" "finance_ops" {
  account_id   = "finance-ops-run"
  display_name = "Finance Ops Cloud Run"
}

resource "google_project_iam_member" "run_bq" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.finance_ops.email}"
}

resource "google_project_iam_member" "run_bq_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.finance_ops.email}"
}

resource "google_project_iam_member" "run_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.finance_ops.email}"
}

resource "google_cloud_run_v2_service" "finance_ops" {
  count    = var.image == "" ? 0 : 1
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.finance_ops.email
    containers {
      image = var.image
      ports {
        container_port = 8080
      }
      env {
        name  = "FINANCE_OPS_DATA_MODE"
        value = "warehouse"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "FINANCE_OPS_BQ_DATASET"
        value = var.dataset_id
      }
      env {
        name  = "FINANCE_OPS_USE_VERTEX_VECTORS"
        value = "false"
      }
      env {
        name  = "FINANCE_OPS_GRAPH_BACKEND"
        value = "duckdb"
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_PERCENT"
    percent = 100
  }
}

resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = var.image == "" ? toset([]) : toset(var.invoker_members)
  name     = google_cloud_run_v2_service.finance_ops[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value
}

# L4 Vector Search — bucket for index embeddings export
resource "google_storage_bucket" "vector_embeddings" {
  name                        = "${var.project_id}-finance-ops-embeddings"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

output "dataset_id" {
  value = google_bigquery_dataset.finance_ops.dataset_id
}

output "pubsub_topic" {
  value = google_pubsub_topic.finance_events.name
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}"
}

output "service_account_email" {
  value = google_service_account.finance_ops.email
}

output "cloud_run_uri" {
  value = try(google_cloud_run_v2_service.finance_ops[0].uri, null)
}

output "embeddings_bucket" {
  value = google_storage_bucket.vector_embeddings.url
}
