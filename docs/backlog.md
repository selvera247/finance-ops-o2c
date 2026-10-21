# Backlog (post master plan + parking lot)

**As of:** 2026-10-21  

## Production spike A — cash app

| Item | Status |
| --- | --- |
| Sample + loader + HITL apply | **Done** (`data/spike_a`, `request_cash_app_approval`) |
| Slack webhook on cash-app notify | Optional polish (`.env` + dotenv load) |
| BigQuery load for Cloud Run | Optional (`load_spike_a.py --bigquery-only`) |
| Spike B portal extract | Not started |

## Agent Engineer craft

| ID | Item | Status |
| --- | --- | --- |
| **C1** | **Read-only MCP** | **Done** — `python -m finance_ops.mcp` · [mcp.md](mcp.md) |
| **C7** | **Sandboxed code exec (A+B+D)** | **Done** — [sandbox.md](sandbox.md); **C7-C** containers later |
| **C3** | **Shadow trajectories** | **Done** — [shadow-trajectories.md](shadow-trajectories.md) |
| **C2** | **3-tier memory + eviction** | **Done** — [memory.md](memory.md) |
| C4–C6 | Context budget · sanitize · self-heal | Later |

## Hygiene

Merge leftover doc branches · bootstrap sqlite · delete unused Agent Engine · revoke PATs · one-pager refresh.
