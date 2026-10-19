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

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_bigquery_dataset" "finance_ops" {
  dataset_id = var.dataset_id
  location   = var.region
}

# Table DDL is applied via data_plane/warehouse/bq_schema.sql (bq CLI) after dataset create.
# Keeping schema in SQL avoids Terraform drift on demo column tweaks.

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

# Placeholder for Cloud Run agent service — wire image after first container build.
# resource "google_cloud_run_v2_service" "finance_ops" { ... }

output "dataset_id" {
  value = google_bigquery_dataset.finance_ops.dataset_id
}

output "pubsub_topic" {
  value = google_pubsub_topic.finance_events.name
}
