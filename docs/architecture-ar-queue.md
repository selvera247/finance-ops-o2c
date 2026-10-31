# AR Exception Queue — System Architecture (MVP → scale)

**Audience:** Eng · CTO  
**Product:** Governed AR autopilot — feed → triage → HITL → apply (outcome SKUs, not seats)  
**Status:** Minimal production version in-repo; scale path documented below

---

## 1. Architecture (target)

```text
┌─────────────── Ingest ───────────────┐     ┌──────── Control plane ────────┐
│ ERP CSV drop zone                    │     │ ADK agents + RBAC + policy    │
│ Portal CSV / Playwright fallback     │────▶│ Durable DAG (file→Temporal)   │
│ HubSpot webhook / closed-won gaps    │     │ Slack HITL + evidence store   │
└──────────────────────────────────────┘     └──────────────┬────────────────┘
                                                           │
┌─────────────── Data plane ───────────┐                   ▼
│ DuckDB (local/demo) / BigQuery (prod)│◀──── materialize ──┐
│ ar_exceptions · payments · invoices  │                    │
│ portal_extracts · sku_meter_events   │                    │
│ TTL cache (in-proc → Redis/Memorystore)                   │
└──────────────────┬───────────────────┘                    │
                   │                                        │
                   ▼                                        │
         FastAPI Cloud Run  /v1/ar/*  ──────────────────────┘
         MCP read-only (free wedge)
```

**Scale path (not in MVP):** Pub/Sub → Dataflow for ingest; Temporal for durable DAG; Memorystore Redis for cache; BigQuery as SoT; Cloud Scheduler for sync; ERP write-back adapter behind feature flag.

---

## 2. Component structure

| Layer | Component | Responsibility |
| --- | --- | --- |
| Edge | `serving.py` `/v1/ar/*` | HTTP contract for queue, metrics, triage, SKUs |
| Free wedge | MCP `finance_ops_readonly` | Aging / suggest / queue summary — no writes |
| Clean BC | `finance_ops/ar_queue/` | Domain · application · ports · adapters — see [clean-architecture-ar-queue.md](clean-architecture-ar-queue.md) |
| Façades | `services/queue_service` · `sku_catalog` | Thin re-exports for legacy imports |
| Runtime | `ar_feed` · `durable` · `exception_queue` · `hitl` | Feed, DAG, aggregate metrics, approvals |
| Agents | coordinator / payments | Tool routing; HITL write path on payments only |
| Data | DuckDB/BQ warehouse | SoT for AR entities + first-class exception rows |
| Cache | `ar_queue.adapters.ttl_cache` → `runtime/cache` | TTL LRU (Redis-compatible key API) |

---

## 3. Data flow

```text
1. Ingest ERP CSV / portal / HubSpot gap
2. Durable triage: score matches (pure) + gap detect
3. sync_ar_exceptions() upserts ar_exceptions (status=open)
4. Optional: request_cash_app_approval → status=pending_hitl + approval_id
5. Human Approve → apply_payment_match → status=resolved + sku_meter_events(billable)
6. GET /v1/ar/metrics reads cache → warehouse aggregate (matched $, TTA, open count)
```

**Invariant:** money movement never bypasses HITL/policy. Cache is never the SoT for apply.

---

## 4. API design (MVP)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/v1/ar/exceptions` | public demo* | List queue (`status`, `lane`, `limit`) |
| `GET` | `/v1/ar/exceptions/{id}` | public demo* | Fetch one exception |
| `POST` | `/v1/ar/exceptions/sync` | public demo* | Materialize open exceptions from warehouse |
| `GET` | `/v1/ar/metrics` | public demo* | Cached queue metrics |
| `GET` | `/v1/ar/skus` | public demo* | SKU catalog |
| `POST` | `/v1/ar/triage` | public demo* | Alias of durable feed triage |
| `POST` | `/v1/request_cash_app_approval` | public demo* | Paid path entry (HITL) |
| `POST` | `/v1/decide_approval` | public demo* | Human decision → apply |

\*Cloud Run demo is open today; production locks mutating routes behind identity (IAM / API key) — same pattern as governance token.

---

## 5. Database schema (MVP additions)

```sql
ar_exceptions(
  exception_id PK, lane, source_type, source_id, customer_id,
  amount, currency, status, disposition,
  recommended_invoice_id, match_score, match_reasons_json,
  approval_id, workflow_run_id, evidence_id, sku_code,
  payload_json, opened_at, updated_at, resolved_at
)

sku_meter_events(
  event_id PK, sku_code, exception_id, customer_id,
  quantity, unit, status, created_at, meta_json
)
```

Existing `payments` / `invoices` / `portal_extracts` remain source tables. `ar_exceptions` is the **product queue projection**.

---

## 6. Caching strategy

| Key pattern | TTL | Invalidation |
| --- | --- | --- |
| `ar:metrics:v1` | 15s | sync, triage, decide_approval |
| `ar:exceptions:list:{status}:{lane}` | 10s | sync, status change |
| `ar:match:{payment_id}` | 60s | payment upsert / apply |

**MVP:** process-local TTL LRU (`finance_ops.runtime.cache`).  
**Prod:** same key API → Redis/Memorystore; multi-instance Cloud Run safe.

Never cache approval decisions or apply results as authoritative.

---

## 7. SKU mapping (minimal)

| Code | Tier | Bill when |
| --- | --- | --- |
| `free.visibility` | Free | Never (aging / list / MCP) |
| `resolve.cash_app` | Paid | Exception `resolved` via cash-app apply |
| `resolve.portal` | Paid | Portal exception resolved |
| `retainer.ar_ops` | Paid | Manual / weekly (metered externally in MVP) |

---

## 8. Minimal production version (what shipped)

- Schema + repository helpers for `ar_exceptions` / `sku_meter_events`
- Clean architecture package `finance_ops/ar_queue` + façades — [clean-architecture-ar-queue.md](clean-architecture-ar-queue.md)
- `sync_from_warehouse` + list/get/metrics use cases
- TTL cache wired to metrics/list (cache-before-ensure on hits)
- Batch scoring + batch upsert + portal one-scan — see [performance-ar-queue.md](performance-ar-queue.md)
- HTTP `/v1/ar/*` + triage hooks that sync after DAG
- Architecture doc (this file) + tests

**Explicitly deferred:** Redis, Temporal, ERP write-back, tenant isolation, billing ledger export.
