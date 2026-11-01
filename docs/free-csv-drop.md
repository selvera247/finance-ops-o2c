# Free visibility — drop two CSVs

**Business offer:** Prospect sends unmatched payments + open AR. You (or the API) return a readout of open $ and suggested matches. **No Cloud Run URL required** for the customer. Nothing is applied.

SKU: `free.visibility`

---

## What they send

1. **Unmatched payments CSV** — cash that isn’t cleared  
2. **Open AR / invoices CSV** — open (and past-due) invoices  

### Payment columns (aliases accepted)

`payment_id` (or txn_id) · `customer_id` (or account_id) · `amount` · `reference`/`memo` · optional `currency`, `status`, `received_at`

### Invoice columns (aliases accepted)

`invoice_id` · `customer_id` · `amount`/`open_amount`/`balance` · `status` · optional `po_number`, dates, `customer_name`

Samples: `data/ar_feed/erp_unmatched_payments.csv` + `data/ar_feed/erp_open_ar.csv`

---

## Run locally (email-ready markdown)

```bash
PYTHONPATH=. python scripts/free_visibility_report.py \
  --payments path/to/unmatched.csv \
  --invoices path/to/open_ar.csv \
  --company "Acme AR" \
  --out /tmp/acme_free_visibility.md \
  --json-out /tmp/acme_free_visibility.json
```

Paste the `.md` into email/Slack. CTA in the footer: suggestions only — pay to clear.

---

## HTTP (free — no Bearer)

After deploy of this change:

```bash
BASE=https://finance-ops-301858971164.us-central1.run.app
curl -s -X POST "$BASE/v1/ar/free_visibility" \
  -F "payments_csv=@unmatched.csv" \
  -F "invoices_csv=@open_ar.csv" \
  -F "company_name=Acme AR" | jq -r .markdown
```

Still **your** ops tool or a thin landing page that posts the two files — customers don’t need `/docs`.

---

## What you give back (business)

| In the report | Meaning |
| --- | --- |
| Snapshot $ | Open unmatched cash vs open AR |
| Top suggested matches | Payment → invoice + why |
| Orphans | Cash with no candidate |
| CTA | Free suggestions; clear via paid HITL later |

Never included: apply, Slack Approve, ERP write-back.
