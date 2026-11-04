#!/usr/bin/env python3
"""Spike A → Copilot vertical slice: sync → investigate → accept → guidance.

Usage:
  PYTHONPATH=. python scripts/load_spike_a.py --replace-customers
  PYTHONPATH=. python scripts/copilot_spike_a_e2e.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Guidance-only for the script unless caller set the demo flag.
os.environ.setdefault("COPILOT_MODE", "workbench")
os.environ.setdefault("COPILOT_EMAIL_EVIDENCE", "0")
os.environ.setdefault("FINANCE_OPS_DEMO_APPLY", "0")


def _reset_cash_app_exceptions() -> None:
    """Drop prior Copilot/HITL statuses so Spike A sync reopens clean cases."""
    from data_plane.warehouse import db

    db.init_schema()
    db.execute("DELETE FROM ar_exceptions WHERE lane = 'cash_app'")


def main() -> int:
    from scripts.load_spike_a import load as load_spike_a
    from finance_ops.copilot import service as copilot
    from finance_ops.copilot.types import Decision, DecisionRequest

    load_spike_a(replace_customers=True)
    _reset_cash_app_exceptions()
    sync = copilot.ensure_queue(sync=True, force=True)
    print("sync", json.dumps({"synced_count": sync.get("synced_count")}, default=str))

    case_id = copilot.case_id_for_payment("PAY-1001")
    queue = copilot.list_queue(sync_first=False, limit=100)
    ids = {c["case_id"] for c in queue.get("cases") or []}
    if case_id not in ids:
        print("ERROR: expected", case_id, "in queue; got", sorted(ids)[:10])
        return 1

    inv = copilot.investigate(case_id, actor="e2e")
    assert inv.get("status") == "success", inv
    assert inv["hypothesis"]["lines"], inv
    assert inv["hypothesis"]["citation_map"], inv

    dec = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.accept, actor="e2e"),
    )
    assert dec.get("status") == "success", dec
    assert dec.get("warehouse_applied") is False
    assert dec.get("auto_apply_fired") is False
    assert dec.get("guidance"), dec
    assert dec.get("case_status") == "ready_to_apply"

    audit = copilot.get_audit(case_id)
    assert any(e.get("event") == "decision" for e in audit.get("audit") or [])

    print(
        json.dumps(
            {
                "case_id": case_id,
                "recommendation": inv["hypothesis"]["lines"][0]["invoice_id"],
                "case_status": dec["case_status"],
                "guidance_payment": dec["guidance"]["payment_id"],
                "warehouse_applied": dec["warehouse_applied"],
            },
            indent=2,
        )
    )
    print("OK — Copilot Spike A E2E guidance-only path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
