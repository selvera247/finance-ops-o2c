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
| **C7** | **Sandboxed code exec (A+B+D+C)** | **Done** — [sandbox.md](sandbox.md); Docker/gVisor via `FINANCE_OPS_SANDBOX_ISOLATION` |
| **C3** | **Shadow trajectories** | **Done** — [shadow-trajectories.md](shadow-trajectories.md) |
| **C2** | **3-tier memory + eviction** | **Done** — [memory.md](memory.md) |
| C4–C6 | Context budget · sanitize · self-heal | Later |

## Hygiene

| Item | Status |
| --- | --- |
| Revoke chat-exposed PATs | **You** (settings/tokens) |
| Delete merged `cursor/*` remote branches | Optional cleanup (15+ safe-delete) |
| Slack `.env` load before HITL notify | **This PR** (`slack_hitl._ensure_dotenv`) |
| One-pager refresh | **This PR** |
| Drop stale `cursor/backlog-a24d` | **This PR** (remote delete) |
| Delete idle Agent Engine | GCP — see [demo-teardown.md](demo-teardown.md) § Agent Engine |
| Bootstrap sqlite | Already live via `POST /v1/bootstrap` post-teardown |
