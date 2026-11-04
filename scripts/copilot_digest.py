#!/usr/bin/env python3
"""Generate optional Copilot exception digest (off by default).

Examples:
  # Dry-run payload even when COPILOT_DIGEST_ENABLED=0
  PYTHONPATH=. python scripts/copilot_digest.py --force

  # Production-style: enable via env, write artifact, optional send stub
  COPILOT_DIGEST_ENABLED=1 PYTHONPATH=. python scripts/copilot_digest.py --sync

  COPILOT_DIGEST_ENABLED=1 COPILOT_DIGEST_SEND=1 \\
    PYTHONPATH=. python scripts/copilot_digest.py --send
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Build digest even when COPILOT_DIGEST_ENABLED is off",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync warehouse exceptions into Copilot queue first",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Invoke send stub (still no real Slack/SMTP post)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--min-confidence",
        default=None,
        choices=["high", "medium", "low", "insufficient"],
        help="Override COPILOT_DIGEST_MIN_CONFIDENCE",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args(argv)

    from finance_ops.copilot.digest import run_digest

    result = run_digest(
        sync_first=args.sync,
        force=args.force,
        send=args.send,
        limit=args.limit,
        min_confidence=args.min_confidence,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result.get("text") or "")
        if result.get("delivery"):
            channels = (result["delivery"] or {}).get("channels") or {}
            print(
                f"\nartifact={channels.get('file_json')} "
                f"send_enabled={result['delivery'].get('send_enabled')}"
            )
        if result.get("status") == "disabled":
            print(
                "\nDigest off by default (alert fatigue). "
                "Set COPILOT_DIGEST_ENABLED=1 or pass --force.",
                file=sys.stderr,
            )
            return 0
    return 0 if result.get("status") in {"success", "disabled"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
