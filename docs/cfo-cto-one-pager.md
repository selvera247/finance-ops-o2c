# Finance Ops Agents — CFO / CTO one-pager

**Audience:** CFO (control & risk) · CTO / Head of Data (architecture) · PSO interview panel  
**Status:** Master plan complete · GitHub `finance_agents` · Slack HITL + **live Cloud Run**  
**Date:** 2026-10  
**Live API:** https://finance-ops-301858971164.us-central1.run.app/docs

---

## 60-second talk track

> “We don’t put a chatbot on PDFs. We put specialists on a **warehouse**, with **evidence** on every material call, a **human gate** for write-offs (Slack Approve/Reject), and a **GUI fallback** when the bank has no API. Same contracts run locally and on **Cloud Run** — aging for Acme returns $16,700 with an evidence id.”

---

## The problem (30 seconds)

AR exceptions, unmatched cash, and legacy portals still burn analyst hours. Most “AI for finance” demos are chat over PDFs. **The gap is governed Data → AI**: agents on a warehouse, with evidence, human gates, and a path when APIs do not exist.

## What we built (demo you can run)

| Layer | Live today |
| --- | --- |
| Data plane | DuckDB · BigQuery mode (L3, DuckDB fallback) |
| Portal unlock | Playwright mock bank + CSV drop zones |
| Agents | ADK coordinator + invoice / payments / contracts / reconciliation |
| Governance | `evidence_id` · write-offs → `needs_review` |
| Runtime | Fallback · breaker · durable DAG · typed A2A · **Slack HITL** |
| Cloud | **Cloud Run** FastAPI (`/health`, `/v1/aging`, `/v1/bootstrap`) |
| AgentOps | pytest + L2 trajectory dry-run CI |
| Narrative | This one-pager (L7) |

**Validated live:**

- Aging `CUST-ACME` → **$16,700** (ADK + Cloud Run)
- `PAY-9002` → `INV-1002` with **`needs_review`**
- Write-off **$125** → Slack `#all-demo` → Approve
- Cloud Run continuous deploy from GitHub (`finance_ops` in `us-central1`)

## Architecture (one picture)

```text
ERP JSON + portal CSVs / GUI
        → warehouse (DuckDB · BigQuery when configured)
        → features / KG / RAG
        → ADK multi-agent + evidence
        → Slack HITL / circuit / durable resume
        → Cloud Run HTTP API (live)
```

## CFO answers

| Question | Answer |
| --- | --- |
| Can it silently write off cash? | **No.** Write-offs flag `needs_review` and open a Slack approval. |
| Audit trail? | Yes — `.evidence/EVD-*.json` + HITL `APPR-*.json` (actor + timestamps). |
| Who owns the decision? | Human for money movement; agent recommends with cited sources. |
| What’s the control story? | Circuit breaker; expiring approvals; token-gated resume links. |

## CTO answers

| Question | Answer |
| --- | --- |
| Why not “just an LLM”? | Tools read a **data plane**; specialists are routable; RAG/KG are pluggable. |
| No API on the bank? | **Fallback router:** API → warehouse → Playwright GUI extract. |
| Production path? | Cloud Run URL live; BigQuery mode + Slack webhook + Terraform. |
| How do we prevent regressions? | CI: unit tests + trajectory dry-run pass-rate gate. |

## Trade-offs we own

- Local DuckDB latency vs BigQuery freshness (mode switch, not rewrite).
- Local / Vertex-shaped vectors vs full Matching Engine endpoint (optional next).
- Auto-match score vs human review cost (`needs_review` threshold).
- File-checkpoint durable DAG vs managed Temporal.
- Slack link buttons need a reachable HITL URL (localhost desktop; ngrok for phone).

## Done vs parking lot

| Done (master plan) | Optional parking lot |
| --- | --- |
| L7 narrative · L3 BQ mode · Slack HITL | Live BQ API + table load |
| L4/L5/L6 code + **Cloud Run live** | Matching Engine endpoint · managed Neo4j |
| Data→AI demo + CI | ADK Agent Engine on same image · craft items (MCP, memory, …) |

## Ask / next conversation

Pick one production spike with a real AR exception queue: **cash app matching** or **portal extract for one carrier/payer**. Evidence + Slack HITL first; deepen BQ / Vector Search without changing agent contracts.

---

*Repo: `selvera247/finance_agents` · Status: [master-plan-status.md](master-plan-status.md)*
