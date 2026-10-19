#!/usr/bin/env python3
"""Load demo JSON tables into BigQuery (L3) or dry-run the plan.

Usage:
  PYTHONPATH=. python scripts/load_bigquery_demo.py --dry-run
  GOOGLE_CLOUD_PROJECT=my-proj PYTHONPATH=. python scripts/load_bigquery_demo.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from data_plane.config import DATA_DIR, bigquery_dataset, gcp_project
    from data_plane.warehouse.bq_adapter import bq_ping

    project = gcp_project()
    dataset = bigquery_dataset()
    tables = {
        "invoices": DATA_DIR / "invoices.json",
        "payments": DATA_DIR / "payments.json",
        "contracts": DATA_DIR / "contracts.json",
    }
    plan = {
        "project": project,
        "dataset": dataset,
        "tables": {name: str(path) for name, path in tables.items()},
        "ping": bq_ping(),
    }
    print(json.dumps(plan, indent=2))

    if args.dry_run or not plan["ping"].get("ok"):
        print("Dry-run / BQ unavailable — no rows loaded.")
        return 0 if args.dry_run or not project else 1

    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    for table_name, path in tables.items():
        rows = json.loads(path.read_text(encoding="utf-8"))
        table_id = f"{project}.{dataset}.{table_name}"
        errors = client.insert_rows_json(table_id, rows)
        print(f"{table_id}: inserted={len(rows)} errors={errors}")
        if errors:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
