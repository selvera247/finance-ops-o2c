# AR feed samples + free CSV drops

| File | Role |
| --- | --- |
| `erp_unmatched_payments.csv` | Unmatched cash (cash-app free wedge) |
| `erp_open_ar.csv` | Open AR / invoices sample |
| `crm_closed_won.csv` | CRM closed-won sold amounts (leakage free wedge) |
| `hubspot_gaps.json` | Offline HubSpot sold fixture for durable triage |
| `templates/` | Blank-ish CSV templates for outreach |

## Free: cash-app visibility

```bash
PYTHONPATH=. python scripts/free_visibility_report.py \
  --payments data/ar_feed/erp_unmatched_payments.csv \
  --invoices data/ar_feed/erp_open_ar.csv \
  --company "Demo" --out /tmp/free_visibility.md
```

## Free: sold-vs-invoiced leakage (CFO wedge)

**Self-serve:** open `/leakage` on the running API (Cloud Run or local uvicorn) — upload two CSVs, no account.

```bash
# Local
uvicorn finance_ops.serving:app --port 8080
# → http://127.0.0.1:8080/leakage

PYTHONPATH=. python scripts/free_leakage_report.py \
  --closed-won data/ar_feed/crm_closed_won.csv \
  --invoices data/ar_feed/erp_open_ar.csv \
  --company "Demo" --out /tmp/free_leakage.md
```

Share pack: [docs/free-leakage-share-pack.md](../../docs/free-leakage-share-pack.md)

## Durable triage (warehouse)

```bash
PYTHONPATH=. python scripts/run_ar_feed_triage.py
```

Does **not** apply matches. HITL apply stays behind write token / Slack Approve.
