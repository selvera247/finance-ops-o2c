# Slice 2 — live AR feed samples

Drop ERP unmatched-payment exports here (or into `data/incoming/ar_exceptions/`)
and/or use the HubSpot gap fixture when no live HubSpot token is configured.

| File | Role |
| --- | --- |
| `erp_unmatched_payments.csv` | ERP/lockbox-shaped unmatched cash → warehouse payments |
| `hubspot_gaps.json` | Fixture closed-won sold amounts by `customer_id` (offline HubSpot gap path) |

## Run durable triage

```bash
PYTHONPATH=. python scripts/run_ar_feed_triage.py
# or stage a custom CSV first:
cp /path/to/export.csv data/incoming/ar_exceptions/
PYTHONPATH=. python scripts/run_ar_feed_triage.py --no-sample
```

Does **not** apply matches. High-confidence suggestions can open HITL via
`request_cash_app_approval` when `--request-hitl` is set.
