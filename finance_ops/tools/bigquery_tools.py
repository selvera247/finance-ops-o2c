from __future__ import annotations

"""BigQuery adapter stub.

Local fixtures are the default. Set FINANCE_OPS_USE_BIGQUERY=true and configure
GOOGLE_CLOUD_PROJECT + FINANCE_OPS_BQ_DATASET to switch tools to live queries.
"""

from typing import Any

from finance_ops.lib.config import bigquery_dataset, gcp_project, use_bigquery


def bigquery_status() -> dict[str, Any]:
    """Report whether BigQuery mode is enabled and which project/dataset apply."""
    enabled = use_bigquery()
    project = gcp_project()
    dataset = bigquery_dataset()
    ready = bool(enabled and project)
    return {
        "status": "success",
        "use_bigquery": enabled,
        "project": project,
        "dataset": dataset,
        "ready": ready,
        "note": (
            "Live BigQuery queries are not wired in this scaffold yet. "
            "Keep FINANCE_OPS_USE_BIGQUERY=false and use fixtures, or extend "
            "this module with google-cloud-bigquery clients."
        ),
        "needs_review": enabled and not ready,
    }
