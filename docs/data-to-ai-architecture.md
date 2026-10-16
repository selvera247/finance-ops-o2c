# End-to-end Data → AI Architecture

One architecture covering analytics, streaming, features/ML, RAG/vectors,
knowledge graph, and agentic execution for finance operations.

```text
 Sources (ERP/JSON)
        │
        ├─ batch ingest ─────────────────────────────┐
        │                                            ▼
        │                                   Warehouse (DuckDB local
        │                                   / BigQuery target)
        │                                            │
 Pub/Sub stand-in (stream simulator) ──► stream_events
        │                                            │
        ▼                                            ├─► Features (customer risk)
  micro-batch flush                                  ├─► Knowledge graph tables
                                                     ├─► Policy docs
                                                     ▼
                                              Vector index
                                         (local hash / Vertex VS)
                                                     │
                                                     ▼
                                         ADK multi-agent system
                                    (coordinator + specialists)
                                                     │
                                                     ▼
                                         Evidence / AgentOps
```

## Layer mapping

| Platform type | Local (runs offline) | GCP production target |
| --- | --- | --- |
| Analytics / warehouse | DuckDB `.warehouse/finance_ops.duckdb` | BigQuery `finance_ops` |
| Streaming | `pipelines/stream/simulator.py` JSONL | Pub/Sub → Dataflow |
| Features / ML | `customer_features` table | Scheduled SQL / Vertex Feature Store |
| GenAI / RAG | hash embeddings + cosine search | Vertex embeddings + Vector Search |
| Knowledge graph | `kg_nodes` / `kg_edges` | Neo4j / Spanner Graph |
| Agentic | Google ADK `finance_ops` | Cloud Run / Agent Runtime |
| Governance | `.evidence/EVD-*.json` | Central audit + tracing |

## Run the full local stack

```bash
PYTHONPATH=. python scripts/run_e2e_data_to_ai.py
# then
adk run finance_ops
# or L2
PYTHONPATH=. python evals/run_trajectory_eval.py --dry-run
```

Env:

```bash
FINANCE_OPS_DATA_MODE=warehouse   # default for E2E
# FINANCE_OPS_DATA_MODE=bigquery  # after Terraform + load
GOOGLE_API_KEY=...                # AI Studio for live agents
```

## Client narrative (5 minutes)

1. **Data plane first** — agents sit on governed warehouse tables, not PDFs alone.
2. **Batch + stream** — same facts, different latency paths.
3. **Features** — risk bands feed collections prioritization.
4. **Vectors + graph** — policies + multi-hop entity reasoning.
5. **Agents + evidence** — tool-backed answers with `evidence_id` and human review.
