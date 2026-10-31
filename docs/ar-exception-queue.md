# Primary leverage — AR exception queue product

**Status:** Next product bet (post master plan)  
**Audience:** Product · CFO buyer · engineering  
**Related:** [backlog.md](backlog.md) · [cfo-cto-one-pager.md](cfo-cto-one-pager.md) · Spike A/B ops docs

---

## Thesis (one paragraph)

Do **not** ship another per-seat AR dashboard. Productize the **real AR exception queue**: feed → triage → Slack approve → apply. Give away visibility (aging, MCP read, HubSpot enrich, shadow proposals). Charge for completed work (matched payments / resolved exceptions), HITL SLAs, durable reconcile, and optional weekly human AR ops. Reuse the same governance runtime for adjacent niches (portal remittance, sold-vs-invoiced leakage, collections coaching) without rebuilding controls.

Lead with the existing CFO story: evidence on every material call, human gates for money movement, GUI fallback when there is no API.

---

## Correct cash-app path (naming)

| Surface | Function | Use |
| --- | --- | --- |
| Agent / product entry | `request_cash_app_approval` | Suggest → open Slack/HITL → apply on approve (or rare policy auto-allow) |
| Internal write | `apply_payment_match` | Warehouse/BQ: mark payment matched to invoice — **not** the LLM/MCP entrypoint |
| Free / read | `list_unmatched_payments`, `suggest_payment_match`, MCP read tools, HubSpot enrich/compare, `shadow_cash_app_trajectory` | No money movement |

Policy defaults direct `apply_payment_match` to `require_human`. MCP must stay read-only (no apply, no HITL decide). Silent auto-write-offs are out of scope.

Proven Spike A loop: suggest → HITL approve → apply (`PAY-1001` → `INV-84219`).

---

## Product loop

```text
Feed (ERP export / portal CSV / HubSpot gap / unmatched cash)
  → Triage (specialists + scores + evidence_id)
  → Shadow (optional; no side effects)
  → request_cash_app_approval → Slack Approve / Reject
  → apply_payment_match (post-approve) + audit artifacts
  → Metric: resolved exception / matched $ / time-to-approve
```

### Free wedge (acquisition)

- Aging (`/v1/aging`, invoice specialist)
- Read-only MCP warehouse tools
- HubSpot enrich / sold-vs-contracted-vs-invoiced compare (read)
- Shadow proposals (recommend only)

### Paid work (SKU)

| SKU | What buyer pays for | Pricing shape |
| --- | --- | --- |
| Agent resolve | Matched payment / cleared exception after HITL | Per resolved exception or matched $ |
| Apply pipelines | Durable cash-app + reconcile runs with evidence | Usage / outcome pack |
| HITL SLA | Guaranteed Slack response path / escalation | Tiered monthly |
| Human AR ops | Weekly coaching / judgment / hard exceptions | Weekly or monthly retainer |
| ERP write-back | Apply beyond warehouse into system of record | Outcome + integration fee |

Enterprise hybrid: compressed platform fee for Cloud Run / security / audit is fine; do not lead GTM with seats in a dashboard.

---

## Studio reuse (same controls)

Reuse fallback · breaker · HITL · shadow · sandbox · memory · sanitize · RBAC · evidence:

| Niche | Free surface | Paid outcome |
| --- | --- | --- |
| AR / cash app (primary) | Aging + unmatched list | Matched payments / cleared exceptions |
| Portal remittance (Spike B) | Extract inbox | Classified remittance + HITL apply |
| Sold vs invoiced (HubSpot) | Compare / enrich views | Resolved leakage / credit memo ops |
| Collections coaching | Aging visibility | Weekly human + agent chase plan |

Do not open a second niche until the primary queue converts (feed → paid resolve).

---

## Build slices (ordered)

1. **Queue story** — **Done.** One narrative + metrics over Spike A + Spike B (matched $, pending approvals, time-to-approve). No dashboard chrome.
2. **Live feed** — **Done.** ERP CSV drop zone + HubSpot sold-vs-invoiced gaps → durable triage (no auto-apply).
3. **SKU + policy** — **MVP done** (catalog + meter on resolve). Full billing export still deferred.
4. **Pilot** — One mid-market AR team or one carrier/payer; price per cleared exception.
5. **Studio expansion** — Only after conversion: second free niche on the same runtime.

### Slice 1 — how to run

```bash
PYTHONPATH=. python scripts/load_spike_a.py
PYTHONPATH=. python scripts/load_spike_b.py
PYTHONPATH=. python scripts/ar_exception_queue.py          # markdown narrative
PYTHONPATH=. python scripts/ar_exception_queue.py --json   # full snapshot

# HTTP (local or Cloud Run after deploy)
curl -s http://127.0.0.1:8080/v1/ar_exception_queue | jq .metrics
```

| Surface | Entry |
| --- | --- |
| Tool / agents | `ar_exception_queue_summary` (coordinator + payments; read-only) |
| MCP | same name on `finance_ops_readonly` |
| HTTP | `GET /v1/ar_exception_queue?markdown=true` |
| Metrics | `matched_usd`, `open_exception_usd`, `pending_approvals`, `time_to_approve_seconds` |

### Slice 2 — live feed → durable triage

```bash
# Stages sample ERP CSV + fixture HubSpot gaps, runs durable DAG
PYTHONPATH=. python scripts/run_ar_feed_triage.py
PYTHONPATH=. python scripts/run_ar_feed_triage.py --request-hitl   # open HITL for high-confidence
PYTHONPATH=. python scripts/run_ar_feed_triage.py --no-live-hubspot

# Or drop a real ERP export:
cp /path/to/unmatched_payments.csv data/incoming/ar_exceptions/
PYTHONPATH=. python scripts/run_ar_feed_triage.py --no-sample
```

| Surface | Entry |
| --- | --- |
| Tool / coordinator | `ingest_ar_feed`, `start_ar_exception_triage` |
| HTTP | `POST /v1/ar_exception_triage` |
| Samples | `data/ar_feed/` · drop zone `data/incoming/ar_exceptions/` |
| DAG steps | ingest → cash-app triage → HubSpot gaps → optional HITL → queue snapshot |

**Does not apply matches.** High-confidence suggestions only open `request_cash_app_approval` when `request_hitl=true`.

Parking-lot GCP (BQ / Matching Engine / Spanner / Agent Engine) lights up only when a real queue customer needs them — not as the product lead.

---

## Non-goals

- Per-seat “knobs and dashboards” as the primary SKU
- Silent auto-apply / auto-write-off of cash
- Exposing `apply_payment_match` on MCP or as the agent’s first tool
- Rebuilding governance per niche

---

## Talk track (buyer)

> We don’t sell seats in another AR screen. We put specialists on your warehouse, cite evidence on every call, and send Slack Approve/Reject before anything is applied. You get aging and recommendations free; you pay when exceptions are resolved — and optionally for a weekly human AR ops retainer when judgment is required. If the bank has no API, we still extract via GUI/CSV.

---

*Repo: `selvera247/finance_agents` · Next scheduling: [backlog.md](backlog.md)*
