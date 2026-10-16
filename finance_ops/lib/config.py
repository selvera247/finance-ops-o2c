from __future__ import annotations

import os

# Re-export data-plane helpers for agent modules
from data_plane.config import (  # noqa: F401
    bigquery_dataset,
    data_mode,
    gcp_project,
)


def use_bigquery() -> bool:
    """When true, tools prefer BigQuery over local JSON fixtures."""
    return data_mode() == "bigquery"


def default_model() -> str:
    return os.getenv("FINANCE_OPS_MODEL", "gemini-flash-latest")
