#!/usr/bin/env python3
"""Drop closed-won + invoices CSVs → free sold-vs-invoiced leakage report.

Usage:
  PYTHONPATH=. python scripts/free_leakage_report.py \\
    --closed-won data/ar_feed/crm_closed_won.csv \\
    --invoices data/ar_feed/erp_open_ar.csv \\
    --company "Acme" --out /tmp/leakage.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Free sold-vs-invoiced leakage report")
    p.add_argument("--closed-won", required=True, help="CRM closed-won / sold CSV")
    p.add_argument("--invoices", required=True, help="Invoices / AR CSV (all or open)")
    p.add_argument("--company", default="")
    p.add_argument("--out", default="")
    p.add_argument("--json-out", default="")
    p.add_argument("--top", type=int, default=25)
    args = p.parse_args()

    from finance_ops.runtime.free_leakage_drop import run_free_leakage_drop

    report = run_free_leakage_drop(
        closed_won_csv=args.closed_won,
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
        f"# summary: gaps={s.get('gap_customer_count')} "
        f"leakage_usd={s.get('positive_leakage_usd')} "
        f"sold={s.get('total_sold_usd')}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
