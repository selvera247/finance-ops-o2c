#!/usr/bin/env python3
"""Slice 2 — run durable AR exception triage from ERP feed + HubSpot gaps.

Usage:
  PYTHONPATH=. python scripts/run_ar_feed_triage.py
  PYTHONPATH=. python scripts/run_ar_feed_triage.py --request-hitl
  PYTHONPATH=. python scripts/run_ar_feed_triage.py --no-sample  # use drop-zone only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="AR live feed → durable triage")
    parser.add_argument(
        "--no-sample",
        action="store_true",
        help="Do not stage bundled sample CSV (use data/incoming/ar_exceptions/)",
    )
    parser.add_argument(
        "--request-hitl",
        action="store_true",
        help="Open request_cash_app_approval for high-confidence suggestions",
    )
    parser.add_argument(
        "--notify-slack",
        action="store_true",
        help="Notify Slack when opening HITL (requires webhook)",
    )
    parser.add_argument(
        "--no-live-hubspot",
        action="store_true",
        help="Force fixture HubSpot gap path even if token is set",
    )
    args = parser.parse_args()

    from finance_ops.tools.queue_tools import start_ar_exception_triage

    result = start_ar_exception_triage(
        stage_sample=not args.no_sample,
        request_hitl=args.request_hitl,
        notify_slack=args.notify_slack,
        use_live_hubspot=not args.no_live_hubspot,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
