from __future__ import annotations

import os


def use_bigquery() -> bool:
    """When true, tools prefer BigQuery over local JSON fixtures."""
    return os.getenv("FINANCE_OPS_USE_BIGQUERY", "false").lower() in {
        "1",
        "true",
        "yes",
    }


def gcp_project() -> str | None:
    return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")


def bigquery_dataset() -> str:
    return os.getenv("FINANCE_OPS_BQ_DATASET", "finance_ops")


def default_model() -> str:
    return os.getenv("FINANCE_OPS_MODEL", "gemini-flash-latest")
