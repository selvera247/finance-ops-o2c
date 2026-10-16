"""Local Pub/Sub stand-in: append JSONL events, then micro-batch into DuckDB.

GCP mapping: topic finance-ops-events → Dataflow → BigQuery stream_events / facts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_plane.config import STREAM_DIR, ensure_dirs
from data_plane.warehouse import db


def _events_path() -> Path:
    ensure_dirs()
    return STREAM_DIR / "events.jsonl"


def publish_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_id": f"EVT-{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "payload": payload,
        "event_ts": datetime.now(timezone.utc).isoformat(),
    }
    path = _events_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")
    return event


def seed_demo_stream() -> list[dict[str, Any]]:
    """Emit a few finance events for E2E demos."""
    events = [
        publish_event(
            "invoice.issued",
            {"invoice_id": "INV-1001", "customer_id": "CUST-ACME", "amount": 12500},
        ),
        publish_event(
            "payment.received",
            {"payment_id": "PAY-9002", "customer_id": "CUST-ACME", "amount": 4200},
        ),
        publish_event(
            "payment.unmatched",
            {"payment_id": "PAY-9002", "reference": "PO-8891"},
        ),
        publish_event(
            "collections.escalation",
            {"customer_id": "CUST-NORTH", "invoice_id": "INV-2001", "aging": "61-90"},
        ),
    ]
    return events


def flush_stream_to_warehouse() -> dict[str, Any]:
    """Micro-batch local stream into warehouse.stream_events (Dataflow stand-in)."""
    db.init_schema()
    path = _events_path()
    if not path.exists():
        return {"status": "success", "inserted": 0}

    inserted = 0
    con = db.connect()
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            con.execute(
                """
                INSERT OR REPLACE INTO stream_events
                VALUES (?, ?, ?, ?)
                """,
                [
                    event["event_id"],
                    event["event_type"],
                    json.dumps(event["payload"]),
                    event["event_ts"],
                ],
            )
            inserted += 1
    finally:
        con.close()
    return {"status": "success", "inserted": inserted}


if __name__ == "__main__":
    print(json.dumps({"seeded": seed_demo_stream(), "flush": flush_stream_to_warehouse()}, indent=2))
