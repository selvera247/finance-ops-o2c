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

Canonical table: `portal_extracts`. Drop zones: `data/incoming/<portal_id>/`.

See [docs/runtime-gaps.md](docs/runtime-gaps.md) for checklist mapping (#11/#10/#8/#1/#5/#12).

## Read-only MCP (Cursor / Claude)

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m finance_ops.mcp
```

Docs + Cursor config: [docs/mcp.md](docs/mcp.md) · `.cursor/mcp.json.example`

## Sandboxed calc / Python (C7 A+B+D)

Agent tools `run_sandboxed_calc` / `run_sandboxed_python` return numbers only (policy wall; no apply/HITL). Docs: [docs/sandbox.md](docs/sandbox.md). Container jail (C7-C) is follow-on.

## Shadow trajectories (C3)

`shadow_cash_app_trajectory` / `shadow_spike_a_walkthrough` propose HITL+apply without mutating. Docs: [docs/shadow-trajectories.md](docs/shadow-trajectories.md).

## Memory (C2)

Three-tier `working` / `episodic` / `long_term` with TTL + LRU eviction. Docs: [docs/memory.md](docs/memory.md).

## Craft C4–C6

Context budget · sanitize · self-heal. Docs: [docs/craft-c4-c6.md](docs/craft-c4-c6.md).

## Portfolio master layer (complete)

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
