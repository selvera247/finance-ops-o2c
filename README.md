# Finance Multi-Agent (Google ADK) + GUI Connector

End-to-end **Data → AI** finance ops demo:

- ADK coordinator + invoice / payments / contracts / reconciliation agents
- DuckDB warehouse, streaming simulator, features, vector RAG, evidence
- Playwright GUI connector for a mock legacy bank portal (no API)
- Runtime: fallback router, circuit breaker, HITL stub, durable DAG, typed A2A

## Quick start

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example finance_ops/.env
# set GOOGLE_API_KEY for live agents

PYTHONPATH=. python scripts/run_e2e_data_to_ai.py
PYTHONPATH=. python scripts/run_gui_connector.py
PYTHONPATH=. python scripts/process_incoming.py   # SageSure + payer sample CSVs
PYTHONPATH=. python scripts/run_durable_workflow.py --no-browser
PYTHONPATH=. python -m finance_ops.runtime.hitl_server   # HITL stub :8787
PYTHONPATH=. pytest -q
PYTHONPATH=. python evals/run_trajectory_eval.py --dry-run

adk web --port 8000
```

## Layout

```text
finance_ops/          ADK agents + tools + runtime/
data_plane/           warehouse, features, vectors, repository
pipelines/            batch + stream
gui_connectors/       mock portal + Playwright + CSV ingest
scripts/              e2e + gui + durable runners
docs/                 architecture + runtime-gaps notes
.github/workflows/    CI gate (pytest + trajectory dry-run)
```

## Portal extract prompts (after GUI / process_incoming)

```text
List portal extracts for portal_id=sagesure and cite evidence_id.
Resolve portal data for legacy_bank with fallback and cite path.
Request approval for write-off amount 125 summary small balance.
Run typed A2A aging for CUST-ACME.
Start durable reconcile without browser.
```

### Spike B (payer remittance exceptions)

```powershell
python scripts\load_spike_b.py
# then: spike_b_walkthrough / classify_portal_exception CLM-B1001 /
# request_portal_extract_review / shadow_spike_b_walkthrough
```

Docs: [data/spike_b/README.md](data/spike_b/README.md). Canonical table: `portal_extracts`. Drop zones: `data/incoming/<portal_id>/`.

See [docs/runtime-gaps.md](docs/runtime-gaps.md) for checklist mapping (#11/#10/#8/#1/#5/#12).

## Read-only MCP (Cursor / Claude)

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m finance_ops.mcp
```

Docs + Cursor config: [docs/mcp.md](docs/mcp.md) · `.cursor/mcp.json.example`

## Sandboxed calc / Python (C7 A+B+D+C)

Agent tools `run_sandboxed_calc` / `run_sandboxed_python` return numbers only (policy wall; no apply/HITL). Optional Docker isolation: `bash scripts/build_sandbox_image.sh` then `FINANCE_OPS_SANDBOX_ISOLATION=container`. Docs: [docs/sandbox.md](docs/sandbox.md).

## Shadow trajectories (C3)

`shadow_cash_app_trajectory` / `shadow_spike_a_walkthrough` propose HITL+apply without mutating. Docs: [docs/shadow-trajectories.md](docs/shadow-trajectories.md).

## Memory (C2)

Three-tier `working` / `episodic` / `long_term` with TTL + LRU eviction. Docs: [docs/memory.md](docs/memory.md).

## Craft C4–C6

Context budget · sanitize · self-heal. Docs: [docs/craft-c4-c6.md](docs/craft-c4-c6.md).

## HubSpot (read-mostly CRM context)

Private-app token via env only (`HUBSPOT_ACCESS_TOKEN`). **Never log or commit the token.**

Minimal scopes (granular CRM):

| Scope | Why |
| --- | --- |
| `crm.objects.companies.read` | Account context |
| `crm.objects.deals.read` | Closed-won / stage |
| `crm.objects.line_items.read` | Sold vs contracted |
| `crm.objects.tickets.read` | Open tickets on aging |
| `crm.objects.contacts.write` *(or engagements write as required for tasks/notes)* | HITL task/note create only |

RBAC: **invoice / contracts / reconciliation** get HubSpot **read** tools (scoped composites: `enrich_aging_hubspot`, `compare_sold_contracted_invoiced`, `match_hubspot_company`). Coordinator and payments get **neither**. Write (`create_task` / `create_note`) is runtime/HITL-only, not LLM-allowlisted.

Also: HITL → HubSpot task handoff (soft-fail), `POST /v1/hubspot/webhook` (v3 signature + 5‑min replay; durable run `WF-HS-DEAL-{id}`), email/phone masking + note injection scrub in sanitize.

```powershell
# finance_ops/.env
HUBSPOT_ACCESS_TOKEN=pat-...
HUBSPOT_CLIENT_SECRET=...   # webhook v3 signature
HITL_PUBLIC_BASE_URL=https://your-public-host   # signed webhook URI base
```

## Portfolio master layer (complete)

- **Next product bet:** [docs/ar-exception-queue.md](docs/ar-exception-queue.md) — feed → triage → Slack HITL → apply (not per-seat UI)
- **Slice 1 queue metrics:** `PYTHONPATH=. python scripts/ar_exception_queue.py` · `GET /v1/ar_exception_queue` · tool `ar_exception_queue_summary`
- **Slice 2 live feed:** `PYTHONPATH=. python scripts/run_ar_feed_triage.py` · `POST /v1/ar_exception_triage` · `data/ar_feed/`
- **Feed/triage debug notes:** [docs/debug-ar-feed-triage.md](docs/debug-ar-feed-triage.md)
- **MVP architecture:** [docs/architecture-ar-queue.md](docs/architecture-ar-queue.md) · `GET /v1/ar/exceptions` · `GET /v1/ar/metrics` · `GET /v1/ar/skus`
- **Queue perf:** [docs/performance-ar-queue.md](docs/performance-ar-queue.md) — batch score/upsert, PK lookups, cache-before-ensure
- **Clean architecture:** [docs/clean-architecture-ar-queue.md](docs/clean-architecture-ar-queue.md) — `finance_ops/ar_queue` domain · application · ports · adapters
- **Cloud Run free tier:** [docs/cloud-run-free-tier.md](docs/cloud-run-free-tier.md) — public GETs; writes need `FINANCE_OPS_API_TOKEN`
- **Free CSV drop (cash):** [docs/free-csv-drop.md](docs/free-csv-drop.md)
- **Free leakage (sold vs invoiced):** [docs/free-leakage-share-pack.md](docs/free-leakage-share-pack.md)
- **Checklist:** [docs/master-layer-complete.md](docs/master-layer-complete.md)
- **L7 narrative:** [docs/cfo-cto-one-pager.md](docs/cfo-cto-one-pager.md)
- **L3 BigQuery:** [docs/bigquery-l3.md](docs/bigquery-l3.md) · `scripts/smoke_master_layer.py`
- **HITL → Slack:** [docs/hitl-slack.md](docs/hitl-slack.md)

## Cloud ladder L4–L6 (complete + live)

- **Status:** [docs/master-plan-status.md](docs/master-plan-status.md)
- **Live API:** https://finance-ops-301858971164.us-central1.run.app/health · [/docs](https://finance-ops-301858971164.us-central1.run.app/docs)
- **Overview:** [docs/l4-l5-l6-complete.md](docs/l4-l5-l6-complete.md)
- **L4 Vector Search:** [docs/l4-vector-search.md](docs/l4-vector-search.md)
- **L5 Knowledge graph:** [docs/l5-knowledge-graph.md](docs/l5-knowledge-graph.md)
- **L6 Cloud Run:** [docs/l6-cloud-run.md](docs/l6-cloud-run.md) · `Dockerfile`
- **GCP go-live:** [docs/gcp-go-live.md](docs/gcp-go-live.md)
- **Parking lot (BQ / ME / Spanner / Agent Engine):** [docs/parking-lot-go-live.md](docs/parking-lot-go-live.md) · `bash scripts/go_live_parking_lot.sh`
- Smoke: `PYTHONPATH=. python scripts/smoke_l4_l5_l6.py`
