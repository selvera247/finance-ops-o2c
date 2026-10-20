# L5 — Persisted knowledge graph

## Backends

| `FINANCE_OPS_GRAPH_BACKEND` | Persistence |
| --- | --- |
| `duckdb` (default) | Warehouse `kg_nodes` / `kg_edges` |
| `sqlite` | `.warehouse/knowledge_graph.sqlite` (portable file graph) |
| `neo4j` | Bolt (`NEO4J_URI`) — Cypher production path |

Spanner Graph–shaped relational edges are the duckdb/sqlite tables; Neo4j is the Cypher target.

## Local Neo4j

```bash
docker compose up -d neo4j
export FINANCE_OPS_GRAPH_BACKEND=neo4j
export NEO4J_URI=bolt://127.0.0.1:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=financeops
PYTHONPATH=. python scripts/sync_knowledge_graph.py --export
```

## SQLite (no Docker)

```bash
export FINANCE_OPS_GRAPH_BACKEND=sqlite
PYTHONPATH=. python scripts/sync_knowledge_graph.py
# ADK: graph neighborhood for PAY-9002 / graph_status
```
