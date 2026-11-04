#!/usr/bin/env python3
"""Run Copilot eval scoreboard against Spike A / gold fixtures.

Usage:
  PYTHONPATH=. python evals/copilot/run_scoreboard.py
  PYTHONPATH=. python evals/copilot/run_scoreboard.py --min-citation 0.95
  PYTHONPATH=. python evals/copilot/run_scoreboard.py --json

Does not call LLMs. Uses the deterministic investigate path (CI-safe).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals.copilot.checkers import check_case, summarize_scoreboard  # noqa: E402
from evals.copilot.gold import load_gold_cases  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _prepare_spike(*, replace: bool = True) -> None:
    os.environ.setdefault("COPILOT_MODE", "workbench")
    os.environ.setdefault("COPILOT_EMAIL_EVIDENCE", "0")
    os.environ.setdefault("FINANCE_OPS_DEMO_APPLY", "0")
    # Force deterministic draft even if a key is present in the environment.
    os.environ.setdefault("COPILOT_FORCE_DETERMINISTIC", "1")

    from data_plane.warehouse import db
    from finance_ops.copilot import service as copilot
    from scripts.load_spike_a import load as load_spike_a

    load_spike_a(replace_customers=replace)
    db.init_schema()
    db.execute("DELETE FROM ar_exceptions WHERE lane = 'cash_app'")
    copilot.ensure_queue(sync=True)


def run_scoreboard(*, gold_path: Path | None = None) -> dict[str, Any]:
    from finance_ops.copilot import service as copilot

    gold_set = load_gold_cases(gold_path)
    results = []
    for gold in gold_set.cases:
        case_id = copilot.case_id_for_payment(gold.payment_id)
        inv = copilot.investigate(case_id, actor="eval-scoreboard")
        if inv.get("status") != "success":
            # Still score a synthetic abstain so the harness stays alive.
            hypothesis = {
                "insufficient_data": True,
                "confidence_band": "insufficient",
                "lines": [],
                "citation_map": [],
            }
            evidence = None
            notes_prefix = [f"investigate failed: {inv.get('status')} {inv.get('error')}"]
        else:
            hypothesis = inv.get("hypothesis") or {}
            evidence = inv.get("evidence")
            notes_prefix = []
        result = check_case(gold, hypothesis=hypothesis, evidence=evidence)
        if notes_prefix:
            result.notes = notes_prefix + list(result.notes)
        results.append(result)

    board = summarize_scoreboard(gold_set, results)
    payload = board.to_dict()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["mode"] = os.getenv("COPILOT_MODE", "workbench")
    return payload


def _markdown(board: dict[str, Any]) -> str:
    lines = [
        f"# Copilot scoreboard ({board.get('version')})",
        "",
        f"- cases: **{board['case_count']}** · pass_rate: **{board['pass_rate']}**",
        f"- citation_validity: **{board['citation_validity']}** "
        f"(target ≥ {board['targets'].get('citation_validity', 0.95)})",
        f"- harmful_error_rate: **{board['harmful_error_rate']}** "
        f"(target ≤ {board['targets'].get('harmful_error_rate_max', 0.02)})",
        f"- insufficient_calibration: **{board['insufficient_calibration']}** "
        f"(target ≥ {board['targets'].get('insufficient_calibration', 0.90)})",
        "",
        "| case | cite | harmful | abstain | pass | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in board.get("cases") or []:
        notes = "; ".join(c.get("notes") or []) or "—"
        lines.append(
            f"| {c['case_id']} | {c['citation_valid']} | {c['harmful_error']} | "
            f"{c['abstain_calibrated']} | {c['passed']} | {notes} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=None, help="Path to gold.yaml")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument(
        "--min-citation",
        type=float,
        default=None,
        help="Fail if citation_validity below this (default: gold target)",
    )
    parser.add_argument(
        "--max-harmful",
        type=float,
        default=None,
        help="Fail if harmful_error_rate above this (default: gold target)",
    )
    parser.add_argument(
        "--write-results",
        action="store_true",
        help="Write evals/copilot/results/latest.{json,md}",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Skip Spike A reload (use existing warehouse)",
    )
    args = parser.parse_args(argv)

    if not args.skip_load:
        _prepare_spike()

    board = run_scoreboard(gold_path=args.gold)
    if args.write_results:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "latest.json").write_text(
            json.dumps(board, indent=2), encoding="utf-8"
        )
        (RESULTS_DIR / "latest.md").write_text(_markdown(board), encoding="utf-8")

    if args.json:
        print(json.dumps(board, indent=2))
    else:
        print(_markdown(board))
        print(json.dumps({"targets_met": board["targets_met"], "pass_rate": board["pass_rate"]}))

    min_cite = (
        args.min_citation
        if args.min_citation is not None
        else float(board["targets"].get("citation_validity", 0.95))
    )
    max_harm = (
        args.max_harmful
        if args.max_harmful is not None
        else float(board["targets"].get("harmful_error_rate_max", 0.02))
    )
    ok = (
        board["citation_validity"] >= min_cite
        and board["harmful_error_rate"] <= max_harm
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
