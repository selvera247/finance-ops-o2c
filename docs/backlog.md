# Backlog (post master plan + parking lot)

**As of:** 2026-10-21  

## Production spikes

| Item | Status |
| --- | --- |
| Spike A sample + loader + HITL apply | **Done** |
| Spike A Slack webhook | Ops runbook — [optional-spike-a-ops.md](optional-spike-a-ops.md) |
| Spike A BigQuery load | Ops runbook — [optional-spike-a-ops.md](optional-spike-a-ops.md) |
| **Spike B portal extract** | **Done** — `data/spike_b` · `scripts/load_spike_b.py` |

## Agent Engineer craft

| ID | Item | Status |
| --- | --- | --- |
| **C1** | **Read-only MCP** | **Done** |
| **C7** | **Sandbox A+B+D+C** | **Done** — [sandbox.md](sandbox.md) |
| **C3** | **Shadow trajectories** | **Done** |
| **C2** | **3-tier memory** | **Done** |
| **C4–C6** | Context budget · sanitize · self-heal | **Open on** `cursor/c4-c6-craft-a24d` — merge next |

## Hygiene

| Item | Status |
| --- | --- |
| Revoke chat-exposed PATs | Ongoing |
| Delete merged `cursor/*` remotes | **Done** (kept only `cursor/c4-c6-craft-a24d`) |
| Slack `.env` load | **Done** |
| One-pager refresh | **Done** |
| Drop `cursor/backlog-a24d` | **Done** |
| Delete idle Agent Engine | **Done** |
| Bootstrap sqlite | Live via `/v1/bootstrap` |
