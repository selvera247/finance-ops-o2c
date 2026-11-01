# AR feed samples + free CSV drop

| File | Role |
| --- | --- |
| `erp_unmatched_payments.csv` | Unmatched cash sample |
| `erp_open_ar.csv` | Open AR / invoices sample |
| `hubspot_gaps.json` | Offline HubSpot sold amounts |

## Free visibility (two CSVs → report)

```bash
PYTHONPATH=. python scripts/free_visibility_report.py \
  --payments data/ar_feed/erp_unmatched_payments.csv \
  --invoices data/ar_feed/erp_open_ar.csv \
  --company "Demo" \
  --out /tmp/free_visibility.md
```

Docs: [docs/free-csv-drop.md](../../docs/free-csv-drop.md)

## Durable triage (warehouse)

Drop payments into `data/incoming/ar_exceptions/` or:

```bash
PYTHONPATH=. python scripts/run_ar_feed_triage.py
```

Does **not** apply matches. HITL apply stays behind write token / Slack Approve.
