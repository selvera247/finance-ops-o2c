"""CLI for governance sweeps (Cloud Scheduler / cron).

Usage:
  PYTHONPATH=. python -m finance_ops.governance.cli sweep
  PYTHONPATH=. python -m finance_ops.governance.cli list
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finance ops governance CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sweep", help="Run agent lifecycle sweep (TTL + eval)")
    sub.add_parser("list", help="List registered agents")

    args = parser.parse_args(argv)
    if args.cmd == "sweep":
        from finance_ops.governance.registry import sweep_lifecycle

        out = sweep_lifecycle()
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("status") == "success" else 1
    if args.cmd == "list":
        from finance_ops.governance.registry import list_agents

        print(json.dumps({"agents": list_agents()}, indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
