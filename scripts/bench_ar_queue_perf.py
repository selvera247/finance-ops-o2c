#!/usr/bin/env python3
"""Micro-benchmarks for AR queue hot paths (scoring, sync, cache).

Run from repo root after warehouse ingest::

    FINANCE_OPS_DATA_MODE=warehouse python3 scripts/bench_ar_queue_perf.py
"""

from __future__ import annotations

import statistics
import time
from typing import Any, Callable


def _ms(fn: Callable[[], Any], *, rounds: int = 5, warmup: int = 1) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return {
        "min_ms": round(min(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "max_ms": round(max(samples), 2),
        "rounds": float(rounds),
    }


def main() -> None:
    from data_plane import repository as repo
    from finance_ops.runtime.cache import DEFAULT_CACHE
    from finance_ops.runtime.ar_feed import triage_unmatched_payments
    from finance_ops.services.queue_service import (
        list_exceptions,
        queue_metrics,
        sync_from_warehouse,
    )
    from finance_ops.tools.payment_tools import score_payment_match, score_payments_batch
    from pipelines.batch.ingest import ingest_batch
    from scripts.load_spike_a import load as load_spike_a
    from scripts.load_spike_b import load as load_spike_b

    ingest_batch(run_id="perf-bench-batch")
    load_spike_a(replace_customers=True)
    load_spike_b()
    DEFAULT_CACHE.clear()

    payments = repo.list_payments(unmatched_only=True)
    n = len(payments)
    print(f"unmatched_payments={n}")

    def n_plus_one() -> None:
        for p in payments:
            score_payment_match(str(p["payment_id"]))

    def batch() -> None:
        score_payments_batch(payments)

    results: dict[str, Any] = {
        "score_n_plus_one": _ms(n_plus_one, rounds=3),
        "score_batch": _ms(batch, rounds=5),
        "triage_unmatched": _ms(lambda: triage_unmatched_payments(), rounds=3),
        "sync_from_warehouse": _ms(
            lambda: sync_from_warehouse(
                include_portal=True, include_hubspot_gaps=True
            ),
            rounds=3,
        ),
    }

    sync_from_warehouse(include_portal=True, include_hubspot_gaps=True)

    def list_cold() -> None:
        DEFAULT_CACHE.clear()
        list_exceptions(status="open", limit=50)

    results["list_exceptions_cold"] = _ms(list_cold, rounds=3, warmup=0)
    list_exceptions(status="open", limit=50)  # seed warm
    results["list_exceptions_warm"] = _ms(
        lambda: list_exceptions(status="open", limit=50), rounds=5, warmup=0
    )

    def metrics_cold() -> None:
        DEFAULT_CACHE.clear()
        queue_metrics(use_cache=True)

    results["queue_metrics_cold"] = _ms(metrics_cold, rounds=3, warmup=0)
    queue_metrics(use_cache=True)
    results["queue_metrics_warm"] = _ms(
        lambda: queue_metrics(use_cache=True), rounds=5, warmup=0
    )

    one = _ms(n_plus_one, rounds=3)["median_ms"]
    bat = _ms(batch, rounds=5)["median_ms"]
    speedup = round(one / bat, 1) if bat else float("inf")
    results["score_speedup_x"] = speedup

    for k, v in results.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
