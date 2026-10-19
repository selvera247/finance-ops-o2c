# Finance Ops Agents — CFO / CTO one-pager

**Audience:** CFO (control & risk) · CTO / Head of Data (architecture) · PSO interview panel  
**Status:** Local E2E demo live on GitHub (`finance_agents`) · AI Studio Tier‑1 validated  
**Date:** 2026-10

---

## The problem (30 seconds)

AR exceptions, unmatched cash, and legacy portals still burn analyst hours. Most “AI for finance” demos are chat over PDFs. **The gap is governed Data → AI**: agents on a warehouse, with evidence, human gates, and a path when APIs do not exist.

## What we built (demo you can run)

| Layer | Live today |
| --- | --- |
| Data plane | Batch + stream sim → DuckDB warehouse → features → local vectors |
| Portal unlock | Playwright mock bank + CSV drop zones (`legacy_bank` / SageSure-like / payer) |
| Agents | ADK coordinator + invoice / payments / contracts / reconciliation |
| Governance | Every material tool call → `evidence_id`; write-offs → `needs_review` |
| Runtime | Fallback router · circuit breaker · HITL approvals · durable DAG · typed A2A |
| AgentOps | pytest + L2 trajectory dry-run CI gate |

**Validated live (AI Studio):** aging `CUST-ACME` ($16,700) via typed A2A; `PAY-9002` → `INV-1002` with `needs_review`; HITL write-off `$125` approved in local Slack-stand-in UI (`APPR-…`, `decided_by=hitl_web`).

## Architecture (one picture)

```text
ERP JSON + portal CSVs / GUI
        → warehouse (DuckDB now · BigQuery next)
        → features / KG / RAG
        → ADK multi-agent + evidence
        → HITL / circuit / durable resume
```

## CFO answers

| Question | Answer |
| --- | --- |
| Can it silently write off cash? | **No.** Write-offs flag `needs_review` and can serialize a pending approval. |
| Audit trail? | Yes — `.evidence/EVD-*.json` + HITL `APPR-*.json` with actor timestamps. |
| Who owns the decision? | Human for money movement; agent recommends with cited sources. |
| What’s the control story? | Circuit breaker caps runaway tools; approvals expire; resume is token-gated. |

## CTO answers

| Question | Answer |
| --- | --- |
| Why not “just an LLM”? | Tools read a **data plane**; specialists are routable; RAG/KG are pluggable. |
| No API on the bank? | **Fallback router:** API → warehouse → Playwright GUI extract. |
| Production path? | Same contracts: BigQuery mode, Slack HITL webhooks, Cloud Run / Agent Runtime (Terraform skeleton). |
| How do we prevent regressions? | CI: unit tests + trajectory dry-run pass-rate gate. |

## Trade-offs we own

- Local DuckDB latency vs BigQuery freshness (mode switch, not rewrite).
- Keyword/hash RAG vs Vertex Vector Search recall.
- Auto-match score vs human review cost (`needs_review` threshold).
- File-checkpoint durable DAG vs managed Temporal (shape first, cluster later).

## 90-day roadmap (PSO-shaped)

1. **Now:** Demo + this narrative (interview / workshop ready).  
2. **Next:** BigQuery behind invoice/payment tools; Slack approval buttons.  
3. **Then:** Vertex Vector Search; graph persistence; Cloud Run deploy.  
4. **Optional craft:** MCP tools, memory tiers, shadow trajectory comparator.

## Ask / next conversation

Pick one production spike with a real AR exception queue: **cash app matching** or **portal extract for one carrier/payer**. We instrument evidence + HITL first, then move the warehouse to BigQuery without changing agent contracts.

---

*Repo: `selvera247/finance_agents` · Run: `adk web` · Docs: `docs/architecture.md`, `docs/runtime-gaps.md`*
