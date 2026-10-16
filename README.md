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
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example finance_ops/.env
# Add GOOGLE_API_KEY=... (AI Studio) for live agents

# End-to-end Data → AI (warehouse + stream + features + vectors + tool smoke)
PYTHONPATH=. python scripts/run_e2e_data_to_ai.py

# L0 — tests
PYTHONPATH=. pytest -q
PYTHONPATH=. python evals/run_eval.py

# L2 — Trajectory eval dry-run (no API key)
PYTHONPATH=. python evals/run_trajectory_eval.py --dry-run

# L1 / L2 live — AI Studio
adk run finance_ops
# or: adk web --port 8000
PYTHONPATH=. python evals/run_trajectory_eval.py
```

Architecture: [docs/data-to-ai-architecture.md](docs/data-to-ai-architecture.md)

## Try these prompts

1. What is the open AR aging for Acme Corp (`CUST-ACME`)?
2. Which payments are unmatched, and what should `PAY-9002` match?
3. What are Northwind payment terms and collections notes?
4. Using the knowledge graph, how is `PAY-9002` connected to Acme invoices?
5. Should we write off Northwind’s remaining balance? Cite policy and flag review.

## Layout

```text
finance-multi-agent/
├── finance_ops/                 # ADK agents (coordinator + specialists)
├── data_plane/                  # warehouse, features, vectors, repository
├── pipelines/                   # batch ingest + stream simulator
├── data/                        # source fixtures
├── infra/terraform/             # BigQuery + Pub/Sub + Artifact Registry
├── docs/data-to-ai-architecture.md
├── evals/                       # L0 + L2 trajectory eval
├── scripts/run_e2e_data_to_ai.py
└── tests/
```

## Design choices

| Concern | Choice now | GCP target |
| --- | --- | --- |
| Warehouse | DuckDB (`.warehouse/`) | BigQuery |
| Streaming | Local JSONL simulator | Pub/Sub → Dataflow |
| Features | `customer_features` table | Feature Store / scheduled SQL |
| RAG | Local hash vectors | Vertex Vector Search |
| Graph | Warehouse KG tables | Neo4j / Spanner Graph |
| Agents | Google ADK | Cloud Run / Agent Runtime |
| IaC | `infra/terraform` skeleton | apply to your project |

## Why this portfolio story works

It mirrors a PSO engagement shape: **governed agents on a real finance data plane**, not a generic chatbot. You can discuss cost/latency/safety trade-offs, show evidence IDs in answers, and walk a CFO/CTO through collections → cash app → contract terms → graph reconciliation.

See [docs/architecture.md](docs/architecture.md) for the workshop narrative and roadmap.
