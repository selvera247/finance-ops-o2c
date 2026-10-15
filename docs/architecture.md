# Finance Ops Multi-Agent — Architecture

## Goal

Demo-ready Data-to-AI portfolio system: coordinator + specialist agents for AR
collections, cash application, contracts, and knowledge-graph reconciliation,
with evidence/governance hooks suitable for client architecture conversations.

## Agent topology

```
finance_ops_coordinator
├── invoice_agent          # invoices, aging
├── payments_agent         # cash app / unmatched
├── contracts_agent        # terms, credit, SLA
└── reconciliation_agent   # GraphRAG walks + policy RAG
```

Delegation uses ADK `sub_agents` (LLM-driven routing by specialist
`description` + coordinator `instruction`).

## Data plane (current → target)

| Layer | Scaffold (now) | Production target |
| --- | --- | --- |
| Operational data | `data/*.json` fixtures | BigQuery (`FINANCE_OPS_USE_BIGQUERY`) |
| Pipelines | n/a | Pub/Sub → Dataflow → BigQuery |
| Semantic graph | `knowledge_graph.json` | Neo4j / Spanner Graph + sync jobs |
| Vectors / RAG | keyword search over `rag_corpus.json` | Vertex AI Vector Search + embeddings |
| Runtime | `adk run` / `adk web` | Cloud Run or Vertex Agent Runtime |
| IaC | n/a | Terraform modules (next iteration) |

## Governance / AgentOps

Every tool call can emit an evidence record under `.evidence/EVD-*.json`:

- `evidence_id`, timestamp, agent, action
- inputs / outputs summary
- source citations (`fixture:…`, `policy:…`)
- `needs_review` flag for human escalation

Coordinator tools: `search_policies`, `flag_for_human_review`,
`get_evidence`, `recent_evidence`, `bigquery_status`.

## Client narrative (interview / workshop)

1. **Discovery:** which AR exceptions burn the most analyst time?
2. **Architecture:** agents on a governed data plane, not a chatbot on PDFs.
3. **Trade-offs:** fixture/local latency vs BigQuery freshness; keyword RAG vs
   Vector Search recall; auto-match thresholds vs human review cost.
4. **Safety:** no silent write-offs; evidence required for recommended actions.
5. **Roadmap:** fixtures → BigQuery → Vector Search → GraphRAG → AgentOps evals.

## Test ladder

| Rung | What | Command |
| --- | --- | --- |
| L0 | Fixture/unit smoke | `pytest`, `evals/run_eval.py` |
| L1 | Live chat (AI Studio) | `adk run finance_ops` / `adk web` |
| L2 | Trajectory scoring | `python evals/run_trajectory_eval.py` (`--dry-run` without key) |
| L3+ | BigQuery / Vector / deploy | See roadmap below |

L2 scores each `evals/cases.yaml` case on mentions, `evidence_id`,
`needs_review`, and preferred specialist author. Reports land in
`evals/results/latest.md`.

## Next build increments

1. Wire `google-cloud-bigquery` behind invoice/payment tools (L3).
2. Replace keyword RAG with Vertex embeddings + Vector Search (L4).
3. Persist knowledge graph (Neo4j / Spanner Graph) (L5).
4. Terraform + Cloud Run / Agent Runtime deploy skeleton (L6).
5. Sample CFO/CTO one-pager from eval + architecture notes (L7).
