# Finance Ops Agents — CFO / CTO one-pager

**Audience:** CFO (control & risk) · CTO / Head of Data (architecture) · PSO interview panel  
**Status:** Master plan complete · **AR exception queue MVP live in-repo** (story → feed → projection → perf → clean architecture)  
**Date:** 2026-10-30  
**Live API:** https://finance-ops-301858971164.us-central1.run.app/docs  
**Backlog:** [backlog.md](backlog.md) · **Product bet:** [ar-exception-queue.md](ar-exception-queue.md)

---

## 60-second talk track

> “We don’t sell another AR dashboard seat. We productize the **exception queue**: ERP/HubSpot feed → triage → Slack Approve → apply, with **evidence** on every material call. Visibility is free (MCP + metrics). We charge when an exception is **resolved**. Same contracts run locally and on **Cloud Run** — money movement never bypasses HITL.”

---

## The problem (30 seconds)

AR exceptions, unmatched cash, and legacy portals still burn analyst hours. Most “AI for finance” demos are chat over PDFs. **The gap is governed Data → AI**: agents on a warehouse, with evidence, human gates, and a path when APIs do not exist — sold as **outcomes**, not seats.

## What we built (demo you can run)

| Layer | Live today |
| --- | --- |
| Data plane | DuckDB · BigQuery mode (L3; live load proven) · `ar_exceptions` + `sku_meter_events` |
| Portal unlock | Playwright mock bank + CSV drop zones (`data/ar_feed/`) |
| Agents | ADK coordinator + invoice / payments / contracts / reconciliation |
| Governance | `evidence_id` · write-offs → `needs_review` · Slack HITL · policy-as-code |
| Runtime | Fallback · breaker · durable DAG · sandbox · shadow · memory |
| Product queue | Story metrics · live feed triage · `/v1/ar/*` · SKU catalog |
| Engineering | ~30× batch scoring · clean architecture (`finance_ops/ar_queue`) |
| IDE surface | Read-only MCP (`finance_ops_readonly`) |
| Cloud | **Cloud Run** FastAPI |
| AgentOps | pytest + L2 trajectory dry-run CI |

**Validated:**

- Aging `CUST-ACME` → **$16,700** (ADK + Cloud Run)
- Spike A: `request_cash_app_approval` → Slack HITL → `apply_payment_match` (`PAY-1001` → `INV-84219`)
- Spike B portal remittance on the same HITL gate
- **Slice 1:** queue story + matched $ / pending HITL / time-to-approve
- **Slice 2:** ERP CSV + HubSpot gaps → durable triage (no auto-apply)
- **MVP:** exception projection, TTL cache, SKUs, HTTP `/v1/ar/exceptions|metrics|skus`
- MCP read-only (no apply)

## Architecture (one picture)

```text
ERP CSV / portal / HubSpot gaps
        → durable triage (batch score · classify)
        → ar_exceptions projection (+ TTL cache)
        → Slack HITL (request_cash_app_approval)
        → apply_payment_match + sku_meter_events (billable)
        → Cloud Run /v1/ar/* · MCP read gateway

Clean layers: domain → application → ports ← adapters (DuckDB / cache)
```

## CFO answers

| Question | Answer |
| --- | --- |
| Can it silently write off cash? | **No.** Write-offs flag `needs_review` and open Slack approval. |
| What do we charge for? | **Resolved exceptions** (`resolve.cash_app` / `resolve.portal`) — not seats. Visibility is free. |
| Audit trail? | Yes — `.evidence/EVD-*.json` + HITL `APPR-*.json` + meter events. |
| Who owns the decision? | Human for money movement; agent recommends with cited sources. |
| Control story? | Circuit breaker; expiring approvals; policy thresholds; shadow before apply. |

## CTO answers

| Question | Answer |
| --- | --- |
| Why not “just an LLM”? | Tools read a **data plane**; specialists are routable; queue is a clean BC. |
| Scale of sync/triage? | Batch invoice preload (~30× vs N+1); PK lookups; cache-before-ensure. |
| Structure? | `finance_ops/ar_queue` domain / application / ports / adapters; legacy façades. |
| No API on the bank? | **Fallback:** API → warehouse → Playwright GUI extract. |
| Production path? | Cloud Run live; BigQuery mode + Slack + Terraform. |
| Regressions? | CI: unit + trajectory dry-run; breaker reset between tests. |

## Trade-offs we own

- Local DuckDB latency vs BigQuery freshness (mode switch, not rewrite).
- In-proc TTL cache vs Memorystore (same key API when multi-replica).
- File-checkpoint durable DAG vs managed Temporal.
- Auto-match score vs human review cost (`needs_review` threshold).
- Outcome SKUs vs seat dashboards (product bet).

## Done vs next

| Done | Next |
| --- | --- |
| Master plan · Cloud Run · Slack HITL · Spike A/B | **Pilot** — one AR team / carrier-payer; price per cleared exception |
| Slice 1 story + metrics · Slice 2 live feed | Billing ledger export / Memorystore / Temporal (as needed) |
| MVP projection + SKUs · perf · clean architecture | Studio expansion only **after** queue conversion |

## Ask / next conversation

Spikes and craft are in place. The product is the **AR exception queue**: feed → triage → HITL → apply. Charge for resolved matches (and optional weekly human AR ops). Do not lead with another dashboard seat SKU. Ready for a pilot design conversation (buyer, exception volume, HITL SLA).

---

*Repo: `selvera247/finance_agents` · Product: [ar-exception-queue.md](ar-exception-queue.md) · Arch: [architecture-ar-queue.md](architecture-ar-queue.md) · Clean: [clean-architecture-ar-queue.md](clean-architecture-ar-queue.md)*
