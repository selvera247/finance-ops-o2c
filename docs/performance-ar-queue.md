# AR queue performance

Hot-path optimizations for speed, memory, and scale on the exception queue.

## Bottlenecks found

| Path | Issue | Impact |
|------|--------|--------|
| `score_payment_match` in sync/triage | N+1 `list_invoices` per payment | ~40× slower on bulk feeds |
| `get_payment` / `get_invoice` | Full-table scan then filter | O(n) I/O per lookup |
| `sync_from_warehouse` | Per-row upsert + cache invalidate | ~2s sync; cache thrash |
| Portal lane / sync | `_find_extract` scanned all extracts per claim | O(claims × extracts) |
| `list_exceptions` / `queue_metrics` | `_ensure()` before cache read | Warehouse wake on every hit |

## Strategies shipped

1. **Batch scoring** — `score_payments_batch` preloads open invoices once, scores in memory (`_score_against_invoices`). Used by sync + `triage_unmatched_payments`.
2. **PK lookups** — `get_payment` / `get_invoice` use DuckDB `WHERE UPPER(id)=?`, BQ get helpers, or fixture iteration — not `list_*` + filter.
3. **Batch upsert** — `upsert_exceptions_batch` one connection, chunked existing-row load, single `invalidate_queue_cache`.
4. **Portal one-scan** — map `portal_extracts()` by `external_id`, then classify.
5. **Cache before ensure** — list/metrics return TTL hits without opening DuckDB.

## Benchmark

```bash
FINANCE_OPS_DATA_MODE=warehouse python3 scripts/bench_ar_queue_perf.py
```

Reference (15 unmatched fixture payments, DuckDB warehouse):

| Metric | Median |
|--------|--------|
| score N+1 | ~380 ms |
| score batch | ~12 ms (**~30×**) |
| `sync_from_warehouse` | ~245 ms |
| list cold / warm | ~28 ms / ~0 ms |
| metrics cold / warm | ~66 ms / ~0 ms |

## Scale notes

- Batch upsert chunks `IN (...)` at 200 ids — raise if syncs exceed ~few thousand rows.
- In-proc TTL LRU is fine for single serving process; Memorystore when multi-replica.
- Scoring is CPU-bound after preload; parallelize by customer shard only if invoice sets are large.
- Do not cache HITL decisions or apply results as authoritative.
