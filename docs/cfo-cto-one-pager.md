# Finance Ops Agents — CFO / CTO one-pager

**Audience:** CFO (control & risk) · CTO / Head of Data (architecture) · PSO interview panel  
**Status:** Complete for interview/workshop · GitHub `finance_agents` · AI Studio Tier‑1 + Slack HITL validated  
**Date:** 2026-10

---

## 60-second talk track

> “We don’t put a chatbot on PDFs. We put specialists on a **warehouse**, with **evidence** on every material call, a **human gate** for write-offs (Slack Approve/Reject), and a **GUI fallback** when the bank has no API. Same tool contracts work on DuckDB today and BigQuery tomorrow.”

---

## The problem (30 seconds)

AR exceptions, unmatched cash, and legacy portals still burn analyst hours. Most “AI for finance” demos are chat over PDFs. **The gap is governed Data → AI**: agents on a warehouse, with evidence, human gates, and a path when APIs do not exist.

## What we built (demo you can run)

| Layer | Live today |
| --- | --- |
| Data plane | Batch + stream sim → DuckDB · **BigQuery mode** (L3, DuckDB fallback) |
| Portal unlock | Playwright mock bank + CSV drop zones (`legacy_bank` / SageSure-like / payer) |
| Agents | ADK coordinator + invoice / payments / contracts / reconciliation |
| Governance | Every material tool call → `evidence_id`; write-offs → `needs_review` |
| Runtime | Fallback · circuit breaker · durable DAG · typed A2A · **Slack HITL** |
| AgentOps | pytest + L2 trajectory dry-run CI gate |
| Narrative | This one-pager (L7) |

**Validated live:**

- Aging `CUST-ACME` → **$16,700** via typed A2A + `evidence_id`
- `PAY-9002` → `INV-1002` with **`needs_review`**
- Write-off **$125** → Slack `#all-demo` card → Approve → `APPR-…` / `decided_by=hitl_web`

## Architecture (one picture)

```text
ERP JSON + portal CSVs / GUI
        → warehouse (DuckDB · BigQuery when configured)
        → features / KG / RAG
        → ADK multi-agent + evidence
        → Slack HITL / circuit / durable resume
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
| Production path? | `FINANCE_OPS_DATA_MODE=bigquery` + Slack webhook + Cloud Run skeleton (Terraform). |
| How do we prevent regressions? | CI: unit tests + trajectory dry-run pass-rate gate. |

## Trade-offs we own

- Local DuckDB latency vs BigQuery freshness (mode switch, not rewrite).
- Keyword/hash RAG vs Vertex Vector Search recall.
- Auto-match score vs human review cost (`needs_review` threshold).
- File-checkpoint durable DAG vs managed Temporal (shape first, cluster later).
- Slack link buttons need a reachable HITL URL (localhost for desktop; ngrok for phone).

## What’s done vs next

| Done now | Next cloud depth |
| --- | --- |
| L7 narrative | L4 Vertex Vector Search |
| L3 BigQuery mode + fallback | L5 persisted graph |
| #8 Slack HITL webhook | L6 Cloud Run deploy |
| Local E2E + CI | Optional: MCP, memory tiers |

## Ask / next conversation

Pick one production spike with a real AR exception queue: **cash app matching** or **portal extract for one carrier/payer**. Evidence + Slack HITL first; flip warehouse to BigQuery without changing agent contracts.

---

*Repo: `selvera247/finance_agents` · Run: `adk web` · Checklist: `docs/master-layer-complete.md`*
