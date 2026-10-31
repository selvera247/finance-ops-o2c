# Debug report — AR feed / exception triage (slice 1–2)

**Role:** Senior debugging investigation  
**Scope:** `finance_ops/runtime/ar_feed.py`, durable triage, queue metrics, CI flake on #28  
**Date:** 2026-10-30 (America/Chicago)

---

## Code functionality (intended)

1. **Slice 1** — Aggregate Spike A cash-app + Spike B portal into a read-only queue snapshot (`matched_usd`, pending HITL, time-to-approve).
2. **Slice 2** — Ingest an ERP unmatched-payment CSV (and HubSpot sold-vs-invoiced gaps) into a durable DAG that **suggests** matches and optionally opens HITL — never auto-applies.

---

## Problems found (root causes)

### P0 — Durable `run_id` collision (data loss)

| | |
| --- | --- |
| **What** | `WF-AR-TRIAGE-%Y%m%d%H%M%S` unique only to the second |
| **Why it fails** | Two runs in the same second write the same checkpoint path and overwrite each other |
| **Repro** | Three rapid `start_ar_exception_triage()` calls → duplicate run_ids |
| **Fix** | Append `uuid4().hex[:10]` to run_id |

### P0 — Bulk triage trips process circuit breaker

| | |
| --- | --- |
| **What** | `triage_unmatched_payments` called `suggest_payment_match` (records breaker) per payment |
| **Why it fails** | >25 unmatched payments (or prior tool use in-process) raises `CircuitOpenError` mid-DAG; CI #28 failed the same way across tests |
| **Fix** | Pure `score_payment_match()` for bulk triage; `tests/conftest.py` resets breaker between tests |

### P1 — HITL false positive without amount match

| | |
| --- | --- |
| **What** | `ready_for_hitl` used `score >= 1.0` only |
| **Why it fails** | invoice_id (0.7) + PO (0.4) = 1.1 opens HITL with **no amount agreement** |
| **Fix** | Require reasons ⊇ `{invoice_id_in_reference, amount_within_tolerance}` |

### P1 — Empty drop zone silently re-stages demo CSV

| | |
| --- | --- |
| **What** | `ingest_erp_payment_csv()` auto-staged sample when no files present |
| **Why it fails** | Production re-ingest of demo payments after every empty poll |
| **Fix** | `auto_stage_sample=False` by default; durable step stages explicitly via `meta.stage_sample` |

### P1 — Corrupt CSV rows crash or report false success

| | |
| --- | --- |
| **What** | Bad `amount` raised `ValueError`; empty `payment_id` skipped with `status=success`, `count=0` |
| **Why it fails** | Durable step dies mid-file, or ops thinks ingest succeeded with zero rows |
| **Fix** | Per-row validation → `row_errors[]`; continue other rows; status `error` if nothing upserted |

### P2 — Duplicate pending HITL on re-run

| | |
| --- | --- |
| **What** | `request_hitl=True` twice for same PAY→INV creates two pending approvals |
| **Fix** | Skip pairs that already have pending `cash_app_*` approvals |

### P2 — Processed archive name collision

| | |
| --- | --- |
| **What** | `{timestamp}_{filename}` collide in the same second |
| **Fix** | Include uuid segment in archive name |

### P2 — Fixture HubSpot company ids hit live API

| | |
| --- | --- |
| **What** | `hs-fixture-*` company ids attempted live HubSpot when token present |
| **Fix** | Skip live path for fixture-looking company ids; report `mode` as fixture/live/mixed |

---

## Edge cases covered by fixes/tests

- Rapid concurrent triage runs (unique run_id)
- CSV missing payment_id / invalid amount / missing customer_id
- Empty drop zone without `stage_sample`
- invoice+PO high score without amount (not HITL-ready)
- Second `--request-hitl` for same payment (dedupe)
- Large unmatched set without breaker trip
- Mixed live + fixture HubSpot gap modes

---

## Verification

```bash
PYTHONPATH=. python -m pytest tests/test_ar_feed_triage.py tests/test_exception_queue.py tests/test_debug_ar_feed_hardening.py -q
PYTHONPATH=. python scripts/run_ar_feed_triage.py --no-live-hubspot
```
