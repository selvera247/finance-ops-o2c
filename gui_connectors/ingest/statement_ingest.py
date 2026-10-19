from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_plane.warehouse import db


def ingest_bank_statement_csv(path: str | Path) -> dict[str, Any]:
    """Load a GUI-downloaded bank statement CSV into warehouse.bank_statements."""
    path = Path(path)
    if not path.exists():
        return {"status": "error", "error": f"file not found: {path}"}

    db.init_schema()
    now = datetime.now(timezone.utc)
    rows_written = 0
    con = db.connect()
    try:
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                con.execute(
                    "INSERT INTO bank_statements VALUES (?,?,?,?,?,?,?,?)",
                    [
                        row.get("statement_id"),
                        row.get("account_id"),
                        row.get("txn_date"),
                        row.get("description"),
                        float(row.get("amount") or 0),
                        row.get("currency") or "USD",
                        path.name,
                        now,
                    ],
                )
                rows_written += 1
        run_id = f"gui-ingest-{uuid.uuid4().hex[:10]}"
        con.execute(
            "INSERT OR REPLACE INTO pipeline_runs VALUES (?,?,?,?,?,?)",
            [run_id, "gui_statement_ingest", "success", f"rows={rows_written} file={path.name}", now, now],
        )
        return {
            "status": "success",
            "rows": rows_written,
            "source_file": path.name,
            "run_id": run_id,
        }
    finally:
        con.close()
