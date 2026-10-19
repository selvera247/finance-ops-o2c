# HITL → Slack (#8 hardened)

Local approval store stays the source of truth. Slack is the notify + button surface.

## Env

```bash
# Incoming webhook (simplest)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Or bot token
SLACK_BOT_TOKEN=xoxb-...
SLACK_HITL_CHANNEL=C0123456789

# Public base for Approve/Reject link buttons (ngrok / Cloud Run URL in prod)
HITL_PUBLIC_BASE_URL=http://127.0.0.1:8787
```

## Run

```bash
PYTHONPATH=. python -m finance_ops.runtime.hitl_server
# In ADK: Request approval for write-off amount 125 ...
# Slack card appears with Approve / Reject link buttons → hits HITL server
```

## Endpoints

| Path | Purpose |
| --- | --- |
| `GET /approvals` | Local list UI |
| `GET /approve?id=&token=` | Decide approved (Slack link target) |
| `POST /api/decide` | Programmatic resume |
| `POST /slack/interactions` | Slack interactive payload (value=`id:token:decision`) |
| `GET /api/approval/<id>` | Status by id |

## Agent tools

- `request_approval` — creates `APPR-…` and calls `notify_slack`
- `get_approval` — confirm status after Slack click
- `list_pending_approvals` / `decide_approval`
