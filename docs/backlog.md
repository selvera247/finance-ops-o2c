# Backlog (post master plan + parking lot)

**As of:** 2026-10-30  

Portfolio craft + spikes are complete. **Primary product bet:** real AR exception queue — see [ar-exception-queue.md](ar-exception-queue.md).  
**Slice 1 (queue story + metrics): Done** — `ar_exception_queue_summary` / `GET /v1/ar_exception_queue` / `scripts/ar_exception_queue.py`.  
**Slice 2 (live feed → triage): Done** — `start_ar_exception_triage` / `POST /v1/ar_exception_triage` / `scripts/run_ar_feed_triage.py`.

## Production spikes

| Item | Status |
| --- | --- |
| Spike A sample + loader + HITL apply | **Done** |
| Spike A Slack webhook (HITL notify + approve) | **Done** (validated locally) — [optional-spike-a-ops.md](optional-spike-a-ops.md) |
| Spike A BigQuery load | **Done** (validated; `PAY-1001`/`2001`/`3001` in BQ) — [optional-spike-a-ops.md](optional-spike-a-ops.md) |
| Spike A BQ loader hardening (`received_at` + streaming buffer) | **Done** — merged PR #21 |
| **Spike B portal extract** | **Done** — `data/spike_b` · `scripts/load_spike_b.py` |

## Agent Engineer craft

| ID | Item | Status |
| --- | --- | --- |
| **C1** | **Read-only MCP** | **Done** — `python -m finance_ops.mcp` · [mcp.md](mcp.md) |
| **C7** | **Sandbox A+B+D+C** | **Done** — [sandbox.md](sandbox.md) |
| **C3** | **Shadow trajectories** | **Done** — [shadow-trajectories.md](shadow-trajectories.md) |
| **C2** | **3-tier memory + eviction** | **Done** — [memory.md](memory.md) |
| **C4–C6** | **Context budget · sanitize · self-heal** | **Done** — [craft-c4-c6.md](craft-c4-c6.md) |

## Hygiene

| Item | Status |
| --- | --- |
| Revoke chat-exposed PATs | **Ongoing** |
| Delete merged `cursor/*` remotes | **Done** (re-clean after each merge) |
| Delete `cursor/bq-spike-a-received-at-a24d` | Optional |
| Slack `.env` load | **Done** |
| One-pager refresh | **Done** (2026-10-30 — points at AR exception queue) |
| Drop `cursor/backlog-a24d` | **Done** |
| Delete idle Agent Engine | **Done** |
| Bootstrap sqlite | Live via `/v1/bootstrap` |

## Next — AR exception queue (scheduled product)

Canonical brief: **[ar-exception-queue.md](ar-exception-queue.md)**

| Slice | Status | Notes |
| --- | --- | --- |
| Queue story + metrics | **Done** | Spike A+B story; matched $ / pending HITL / time-to-approve |
| Live feed | **Done** | ERP CSV + HubSpot gaps → durable triage (HITL opt-in) |
| SKUs | **MVP** | Catalog + `sku_meter_events` on resolve — see [architecture-ar-queue.md](architecture-ar-queue.md) |
| Queue projection | **MVP** | `ar_exceptions` table + `/v1/ar/*` APIs + TTL cache |
| Queue perf | **Done** | Batch score/upsert, PK lookups, cache-before-ensure — [performance-ar-queue.md](performance-ar-queue.md) |
| Clean architecture | **Done** | `finance_ops/ar_queue` domain/app/ports/adapters — [clean-architecture-ar-queue.md](clean-architecture-ar-queue.md) |
| Free Cloud Run wedge | **Done** | Public GETs/suggest; writes locked (`FINANCE_OPS_API_TOKEN`) |
| Free two-CSV drop | **Done** | Unmatched + open AR → report — [free-csv-drop.md](free-csv-drop.md) |
| Free leakage wedge | **Done** | Sold vs invoiced gap $ — [free-leakage-share-pack.md](free-leakage-share-pack.md) |
| Pilot | Pending | One AR team / carrier-payer; no per-seat dashboard lead |
| Studio expansion | Later | Portal remittance / collections after primary wedge converts |

**Agent write path:** `request_cash_app_approval` (not direct `apply_payment_match`). MCP stays read-only.
