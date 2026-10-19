# End-to-end Data → AI Architecture

```text
 Sources (ERP/JSON) + Legacy GUI portal
        │
        ├─ batch ingest ────────────────┐
        ├─ GUI connector (Playwright) ──┤
        │                               ▼
        │                      Warehouse (DuckDB / BigQuery)
 Pub/Sub stand-in ──► stream_events     │
                                        ├─ Features
                                        ├─ Knowledge graph
                                        ├─ Vectors / RAG
                                        ├─ bank_statements
                                        ▼
                               ADK multi-agent finance_ops
                                        ▼
                               Evidence / AgentOps
```

See also `docs/gui-connector.md`.
