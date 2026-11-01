#!/usr/bin/env python3
"""Drop two CSVs → free AR visibility report (markdown + JSON). No apply / no Cloud Run URL.

Usage:
  PYTHONPATH=. python scripts/free_visibility_report.py \\
    --payments data/ar_feed/erp_unmatched_payments.csv \\
    --invoices data/ar_feed/erp_open_ar.csv \\
    --company "Acme AR" \\
    --out /tmp/ar_free_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Free visibility report from two CSVs")
    parser.add_argument("--payments", required=True, help="Unmatched payments CSV")
    parser.add_argument("--invoices", required=True, help="Open AR / invoices CSV")
    parser.add_argument("--company", default="", help="Company name for the report header")
    parser.add_argument("--out", default="", help="Write markdown to this path")
    parser.add_argument("--json-out", default="", help="Optional JSON report path")
    parser.add_argument("--top", type=int, default=15, help="Max suggestions/orphans listed")
    args = parser.parse_args()

    from finance_ops.runtime.free_csv_drop import run_free_csv_drop

    report = run_free_csv_drop(
        payments_csv=args.payments,
        invoices_csv=args.invoices,
        company_name=args.company or None,
        top_n=args.top,
    )
    if report.get("status") != "success":
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1

    md = report.get("markdown") or ""
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)

    if args.json_out:
        payload = {k: v for k, v in report.items() if k != "markdown"}
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")

    s = report.get("summary") or {}
    print(
        f"# summary: payments={s.get('unmatched_payment_count')} "
        f"suggested={s.get('suggested_match_count')} "
        f"open_unmatched_usd={s.get('open_unmatched_usd')}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
