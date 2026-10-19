# Finance Multi-Agent (Google ADK) + GUI Connector

End-to-end **Data → AI** finance ops demo:

- ADK coordinator + invoice / payments / contracts / reconciliation agents
- DuckDB warehouse, streaming simulator, features, vector RAG, evidence
- **NEW:** Playwright GUI connector for a mock legacy bank portal (no API)

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
PYTHONPATH=. pytest -q

adk web --port 8000
```

## Layout

```text
finance_ops/          ADK agents + tools
data_plane/           warehouse, features, vectors, repository
pipelines/            batch + stream
gui_connectors/       mock portal + Playwright + CSV ingest
scripts/              e2e + gui runners
docs/                 architecture notes
```

## Portal extract prompts (after GUI / process_incoming)

```text
List portal extracts for portal_id=sagesure and cite evidence_id.
List portal extracts for payer_availity with claim statuses.
List bank statements for ACC-1001 and cite evidence_id.
```

Canonical table: `portal_extracts`. Drop zones: `data/incoming/<portal_id>/`.
