#!/usr/bin/env python3
"""Slice 1 — print AR exception queue story + metrics (Spike A + Spike B).

Usage:
  PYTHONPATH=. python scripts/load_spike_a.py
  PYTHONPATH=. python scripts/load_spike_b.py
  PYTHONPATH=. python scripts/ar_exception_queue.py
  PYTHONPATH=. python scripts/ar_exception_queue.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="AR exception queue metrics")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full JSON snapshot instead of markdown",
    )
    parser.add_argument(
        "--markdown-field",
        action="store_true",
        help="Include markdown inside JSON (implies --json)",
    )
    args = parser.parse_args()

    from finance_ops.tools.queue_tools import ar_exception_queue_summary

    if args.json or args.markdown_field:
        snap = ar_exception_queue_summary(include_markdown=args.markdown_field or True)
        print(json.dumps(snap, indent=2, default=str))
        return 0 if snap.get("status") == "success" else 1

    snap = ar_exception_queue_summary(include_markdown=True)
    print(snap.get("markdown") or json.dumps(snap, indent=2, default=str))
    return 0 if snap.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
