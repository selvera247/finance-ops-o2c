# Finance Multi-Agent (Google ADK)

Portfolio scaffold for a **Data-to-AI finance operations** system:

- Coordinator + specialist agents (invoices, payments, contracts, reconciliation)
- Local fixtures standing in for BigQuery / Vector Search / graph DB
- Evidence & governance hooks for AgentOps demos
- Eval case stubs + architecture notes for client narratives

Built with [Google Agent Development Kit (ADK)](https://adk.dev).

## Quick start

```bash
cd finance-multi-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example finance_ops/.env
# Add GOOGLE_API_KEY=... (AI Studio) or configure Vertex env vars

# L0 — Tool smoke (no API key)
PYTHONPATH=. python scripts/smoke_tools.py
PYTHONPATH=. pytest -q
PYTHONPATH=. python evals/run_eval.py

# L2 — Trajectory eval dry-run (no API key)
PYTHONPATH=. python evals/run_trajectory_eval.py --dry-run

# L1 / L2 live — AI Studio
cp .env.example finance_ops/.env
# set GOOGLE_API_KEY=... in finance_ops/.env
adk run finance_ops
# or: adk web --port 8000
PYTHONPATH=. python evals/run_trajectory_eval.py
# results → evals/results/latest.md
```

## Try these prompts

1. What is the open AR aging for Acme Corp (`CUST-ACME`)?
2. Which payments are unmatched, and what should `PAY-9002` match?
3. What are Northwind payment terms and collections notes?
4. Using the knowledge graph, how is `PAY-9002` connected to Acme invoices?
5. Should we write off Northwind’s remaining balance? Cite policy and flag review.

## Layout

```text
finance-multi-agent/
├── finance_ops/                 # ADK app (root_agent)
│   ├── agent.py                 # coordinator
│   ├── specialists/             # invoice / payments / contracts / reconciliation
│   ├── tools/                   # fixture-backed tools + BQ stub
│   └── lib/                     # fixtures, evidence, config
├── data/                        # invoices, payments, contracts, graph, RAG corpus
├── docs/architecture.md         # client-ready architecture notes
├── evals/                       # cases.yaml + offline tool eval
├── tests/
└── scripts/smoke_tools.py
```

## Design choices

| Concern | Choice now | Next step |
| --- | --- | --- |
| Data | JSON fixtures in `data/` | BigQuery via `FINANCE_OPS_USE_BIGQUERY` |
| RAG | Keyword search over policies | Vertex AI Vector Search |
| Graph | In-memory walk over JSON KG | Neo4j / Spanner Graph + GraphRAG |
| Governance | `.evidence/EVD-*.json` per tool call | Central audit store + tracing |
| Deploy | Local `adk run` / `adk web` | Cloud Run / Agent Runtime + Terraform |

## Why this portfolio story works

It mirrors a PSO engagement shape: **governed agents on a real finance data plane**, not a generic chatbot. You can discuss cost/latency/safety trade-offs, show evidence IDs in answers, and walk a CFO/CTO through collections → cash app → contract terms → graph reconciliation.

See [docs/architecture.md](docs/architecture.md) for the workshop narrative and roadmap.
