# Backlog (post master plan + parking lot)

**As of:** 2026-10-21  

## Production spikes

| Item | Status |
| --- | --- |
| Spike A sample + loader + HITL apply | **Done** |
| Spike A Slack webhook | Optional (`.env`) |
| Spike A BigQuery load | Optional (`load_spike_a.py --bigquery-only`) |
| **Spike B portal extract** | **Done** — `data/spike_b` · `scripts/load_spike_b.py` · [spike_b/README.md](../data/spike_b/README.md) |

## Agent Engineer craft

| ID | Item | Status |
| --- | --- | --- |
| **C1** | **Read-only MCP** | **Done** |
| **C7** | **Sandbox A+B+D+C** | **Done** — [sandbox.md](sandbox.md) |
| **C3** | **Shadow trajectories** | **Done** |
| **C2** | **3-tier memory** | **Done** |
| C4–C6 | Context budget · sanitize · self-heal | Merged if on main; else branch `cursor/c4-c6-craft-a24d` |

## Hygiene

| Item | Status |
| --- | --- |
| Revoke chat-exposed PATs | Ongoing |
| Delete merged `cursor/*` remotes | Optional |
| Slack `.env` load | **Done** |
| One-pager refresh | **Done** |
| Drop `cursor/backlog-a24d` | **Done** |
| Delete idle Agent Engine | **Done** (force delete) |
| Bootstrap sqlite | Live via `/v1/bootstrap` |
