# L4 · L5 · L6 complete

| Level | Deliverable | Local proof |
| --- | --- | --- |
| **L4** | Vertex-shaped vectors + ME simulator | `build_policy_index` + `search_policies` |
| **L5** | GraphStore duckdb/sqlite/neo4j | `scripts/sync_knowledge_graph.py --backend sqlite` |
| **L6** | Cloud Run image + Terraform | `uvicorn finance_ops.serving:app` / `pytest tests/test_l6_serving.py` |

```bash
PYTHONPATH=. python scripts/smoke_l4_l5_l6.py
```

See `l4-vector-search.md`, `l5-knowledge-graph.md`, `l6-cloud-run.md`.
