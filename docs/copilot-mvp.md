# Cash-Application Exception Copilot MVP

**Product north star** for this repo: a permissioned investigation workbench for cash-app exceptions — retrieve evidence, draft a **cited** match hypothesis, human **Accept | Edit & ready-to-apply | Reject | Escalate | Request more info**, emit an **ApplyGuidancePacket** for the current ERP. **AI never posts cash unattended.**

Slack HITL Approve → warehouse apply remains available as a **contrast / notify** path, not the pilot primary UX.

## Quick demo (Spike A)

```bash
PYTHONPATH=. python scripts/load_spike_a.py --replace-customers
PYTHONPATH=. python scripts/copilot_spike_a_e2e.py
# optional UI
uvicorn finance_ops.serving:app --host 0.0.0.0 --port 8080
# open http://127.0.0.1:8080/copilot  and  /docs
```

## HTTP API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/v1/copilot/status` | Mode flags |
| GET | `/v1/copilot/queue` | Ranked cases (`?sync=true` materializes warehouse) |
| GET | `/v1/copilot/cases/{id}` | Case detail + overlay hypothesis |
| GET | `/v1/copilot/cases/{id}/evidence` | Evidence pack |
| POST | `/v1/copilot/cases/{id}/investigate` | Bounded retrieve → rules → draft (write-gated) |
| POST | `/v1/copilot/cases/{id}/hypothesis` | Edit lines (write-gated) |
| POST | `/v1/copilot/cases/{id}/decision` | Decision → guidance / status (write-gated) |
| GET | `/v1/copilot/cases/{id}/audit` | Timeline |

OpenAPI: `/docs`. Thin workbench: `/copilot`.

## Prototype modes A–D

| Mode | Env | What it demos |
| --- | --- | --- |
| **A** | `COPILOT_MODE=workbench` `COPILOT_EMAIL_EVIDENCE=0` | Primary Copilot UX; ERP + remittance only |
| **B** | `COPILOT_MODE=workbench` `COPILOT_EMAIL_EVIDENCE=1` | Same + **stub** email evidence item |
| **C** | `COPILOT_MODE=slack_contrast` | Slack HITL Approve/Reject as **contrast** (not SoT) |
| **D** | `COPILOT_MODE=rules_only` | Deterministic candidates only; skip LLM draft path |

## Guidance-only apply + demo flag

- On **accept** / **edit_ready_to_apply**, Copilot emits `ApplyGuidancePacket` (copy text + deep-link hint) and sets status `ready_to_apply`.
- **Does not** call warehouse apply on the happy path.
- Set `FINANCE_OPS_DEMO_APPLY=1` to optionally apply into DuckDB/BQ for sandbox demos only.
- Policy `auto_allow_max` stays **0**; Copilot path never fires auto-apply from thresholds.

## Statuses

Extended (non-breaking): `ready_to_apply`, `need_info`, `escalated`, `closed_rejected` alongside existing `open` / `pending_hitl` / `resolved` / `rejected`.

## Parked for Weeks 5–8+ (not this foundation)

- Production email ACL / OCR remittance suite
- HubSpot leakage / free `/leakage` as MVP UX
- Portal Spike B as primary path
- Fine-tuning, Neo4j / Vector Search critical path
- Broad ADK multi-agent rewrite; Slack-as-primary decision UI
- Citation-validity / harmful-error gold scoreboard dashboards
- Cross-customer AuthZ hardening beyond allowlist stubs

## Module map

```text
finance_ops/copilot/     types · config · investigate · service · router
finance_ops/ar_queue/    matching · statuses (extended) · sync/queries
finance_ops/serving.py   mounts /v1/copilot/* + /copilot
```
