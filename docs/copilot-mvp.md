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
| GET | `/v1/copilot/cases/{id}/audit` | Timeline + discovery-minimum fields |

OpenAPI: `/docs`. Thin workbench: `/copilot`.

## Prototype modes A–D

| Mode | Env | What it demos |
| --- | --- | --- |
| **A** | `COPILOT_MODE=workbench` `COPILOT_EMAIL_EVIDENCE=0` | Primary Copilot UX; ERP + remittance only |
| **B** | `COPILOT_MODE=workbench` `COPILOT_EMAIL_EVIDENCE=1` | Same + **stub** email evidence item |
| **C** | `COPILOT_MODE=slack_contrast` | Slack HITL Approve/Reject as **contrast** (not SoT) |
| **D** | `COPILOT_MODE=rules_only` | Deterministic candidates only; skip LLM draft path |

Set `COPILOT_FORCE_DETERMINISTIC=1` to keep the structured draft path even when `GOOGLE_API_KEY` is present (CI default via the scoreboard runner).

## Guidance-only apply + demo flag

- On **accept** / **edit_ready_to_apply**, Copilot emits `ApplyGuidancePacket` (copy text + deep-link hint) and sets status `ready_to_apply`.
- **Does not** call warehouse apply on the happy path.
- Set `FINANCE_OPS_DEMO_APPLY=1` to optionally apply into DuckDB/BQ for sandbox demos only.
- Policy `auto_allow_max` stays **0**; Copilot path never fires auto-apply from thresholds.

## Statuses

Extended (non-breaking): `ready_to_apply`, `need_info`, `escalated`, `closed_rejected` alongside existing `open` / `pending_hitl` / `resolved` / `rejected`.

## Eval scoreboard (Weeks 5–6)

Primary quality bar (replaces “mentions + evidence_id” for Copilot drafts):

| Metric | Meaning | Gold target |
| --- | --- | --- |
| **Citation validity** | Every claim citation maps to a retrieved evidence `source_id`, or the draft abstains | ≥ 0.95 |
| **Harmful-error rate** | Wrong invoice/amount if the raw hypothesis were rubber-stamped | ≤ 0.02 (A7 stub) |
| **Insufficient-data calibration** | Abstain when gold says thin/missing evidence; penalize false-confident | ≥ 0.90 |

Gold fixtures: `evals/copilot/gold.yaml` (Spike A seeded). Checkers: `evals/copilot/checkers.py`.

```bash
# Full scoreboard (reloads Spike A, deterministic draft)
PYTHONPATH=. python evals/copilot/run_scoreboard.py --write-results

# JSON only / CI gates
PYTHONPATH=. python evals/copilot/run_scoreboard.py --json --min-citation 0.95 --max-harmful 0.02

# Unit + integration
PYTHONPATH=. pytest tests/test_copilot_scoreboard.py tests/test_copilot_mvp.py -q
```

Results (when `--write-results`): `evals/copilot/results/latest.md` + `latest.json`.

**How to read the scoreboard**

1. `citation_validity` — if this drops, drafts are inventing sources or omitting `citation_map` on non-abstain hypotheses.
2. `harmful_error_rate` — non-zero means a confident draft would post the wrong invoice/amount if Accept were rubber-stamped; fix matching / abstain thresholds before widening pilot.
3. `insufficient_calibration` — false abstain (missed easy matches) or false-confident (proposed on orphan/thin remittance) both hurt trust; prefer abstain over wrong cash.
4. Per-case `notes` in the markdown table explain failures.

**Trajectory evals stay as regression** (RBAC deny / no silent apply):

```bash
PYTHONPATH=. python evals/run_trajectory_eval.py --dry-run --min-pass-rate 0.8
```

CI (`.github/workflows/ci.yml`) runs pytest + trajectory dry-run + Copilot scoreboard.

Accept / edit rate + edit distance are logged via the `decision` audit trail (`raw_hypothesis` vs edited `hypothesis`); dashboard wiring is still lightweight (export audit JSON).

## Hypothesis draft path

`POST .../investigate` always:

1. Loads payment + open invoices (warehouse)
2. Builds an evidence pack (payment, remittance text, invoices, `matching.py` rule candidates; optional email stub)
3. Scores candidates via `matching.py`
4. Emits a **structured** `MatchHypothesis` with `citation_map` pointing only at retrieved evidence ids
5. **Abstains** (`insufficient_data`, `confidence_band=insufficient`) on thin remittance / amount-only weak cues / no candidates
6. Optional LLM summary when `GOOGLE_API_KEY` / `GEMINI_API_KEY` is set and `COPILOT_FORCE_DETERMINISTIC` is off — line items stay deterministic from rules

## Audit minimum fields

Investigate + decision events persist: `case_id`, `customer_id`, `payment_id`, `invoice_ids`, remittance/email ids, `retriever_version`, `model_id` / `prompt_version`, `raw_hypothesis`, edited hypothesis, `decision`, `reason_code`, `actor`, timestamps, `confidence_band`, `citation_map`. See `GET /v1/copilot/cases/{id}/audit`.

## Workbench UX (`/copilot`)

- Citations are clickable → scroll/highlight the evidence item
- Insufficient-data banner disables confident Accept
- Reject / Escalate / Need info require a reason-code select
- ApplyGuidancePacket JSON + copy text shown after Accept / Edit & ready

## Parked (not this slice)

- Production email ACL / OCR remittance suite
- HubSpot leakage / free `/leakage` as MVP UX
- Portal Spike B as primary path
- Fine-tuning, Neo4j / Vector Search critical path
- Broad ADK multi-agent rewrite; Slack-as-primary decision UI
- Cross-customer AuthZ beyond allowlist stubs; digest alerts productization

## Module map

```text
finance_ops/copilot/     types · config · investigate · service · router · store
finance_ops/ar_queue/    matching · statuses (extended) · sync/queries
finance_ops/web/copilot.html
evals/copilot/           gold.yaml · checkers · run_scoreboard.py
finance_ops/serving.py   mounts /v1/copilot/* + /copilot
```
