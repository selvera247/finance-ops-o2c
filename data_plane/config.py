from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
WAREHOUSE_DIR = REPO_ROOT / ".warehouse"
DUCKDB_PATH = Path(os.getenv("FINANCE_OPS_DUCKDB", str(WAREHOUSE_DIR / "finance_ops.duckdb")))
VECTOR_DIR = Path(os.getenv("FINANCE_OPS_VECTOR_DIR", str(WAREHOUSE_DIR / "vectors")))
STREAM_DIR = Path(os.getenv("FINANCE_OPS_STREAM_DIR", str(WAREHOUSE_DIR / "stream")))


def data_mode() -> str:
    """fixtures | warehouse | bigquery

    warehouse = local DuckDB (default for E2E Data→AI demos)
    bigquery  = live GCP BigQuery when configured
    fixtures  = raw JSON only (legacy unit tests)
    """
    raw = os.getenv("FINANCE_OPS_DATA_MODE", "").strip().lower()
    if raw in {"fixtures", "warehouse", "bigquery"}:
        return raw
    # Back-compat with earlier flag
    if os.getenv("FINANCE_OPS_USE_BIGQUERY", "").lower() in {"1", "true", "yes"}:
        return "bigquery"
    return "warehouse"


def gcp_project() -> str | None:
    return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")


def bigquery_dataset() -> str:
    return os.getenv("FINANCE_OPS_BQ_DATASET", "finance_ops")


def ensure_dirs() -> None:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    STREAM_DIR.mkdir(parents=True, exist_ok=True)
