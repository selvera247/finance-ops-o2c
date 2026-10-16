from __future__ import annotations

from typing import Any

from data_plane.config import bigquery_dataset, data_mode, gcp_project
from data_plane.vectors.embed import vertex_vector_status
from data_plane.warehouse import db


def bigquery_status() -> dict[str, Any]:
    """Report data-plane mode and warehouse / BigQuery / vector readiness."""
    mode = data_mode()
    project = gcp_project()
    dataset = bigquery_dataset()
    duck_ready = False
    try:
        from data_plane.config import DUCKDB_PATH

        duck_ready = DUCKDB_PATH.exists()
        counts = {}
        if duck_ready:
            counts = {
                "invoices": db.query_dicts("SELECT COUNT(*) AS n FROM invoices")[0]["n"],
                "payments": db.query_dicts("SELECT COUNT(*) AS n FROM payments")[0]["n"],
                "features": db.query_dicts("SELECT COUNT(*) AS n FROM customer_features")[0][
                    "n"
                ],
                "stream_events": db.query_dicts("SELECT COUNT(*) AS n FROM stream_events")[
                    0
                ]["n"],
            }
    except Exception as exc:  # noqa: BLE001
        counts = {"error": str(exc)}

    return {
        "status": "success",
        "data_mode": mode,
        "project": project,
        "dataset": dataset,
        "duckdb_ready": duck_ready,
        "warehouse_counts": counts,
        "vertex_vectors": vertex_vector_status(),
        "gcp_mapping": {
            "batch": "JSON/sources → Dataflow/batch → BigQuery",
            "stream": "Pub/Sub → Dataflow → BigQuery",
            "features": "scheduled SQL / Vertex Feature Store",
            "vectors": "Vertex AI embeddings + Vector Search",
            "agents": "ADK on Cloud Run / Agent Runtime",
        },
        "needs_review": mode == "bigquery" and not project,
    }
