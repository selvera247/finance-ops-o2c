# Free sold-vs-invoiced leakage — share pack

**O2C wedge:** Revenue leakage (CRM closed-won vs invoiced AR)  
**Free:** gap $ by customer  
**Paid later:** resolve (invoice missing revenue / credit overbill) with human review  

SKU surface: `free.visibility` · lane `sold_vs_invoiced`

---

## 1. One-liner

> Send closed-won and invoices — we’ll show **sold vs invoiced leakage by customer** for free. Nothing is billed or credited. You pay only if you want us to help **resolve** the gaps.

---

## 2. Email

**Subject:** Free sold-vs-invoiced leakage readout (two CSVs)

Hi {Name},

A common O2C leak: **closed-won in CRM doesn’t match what was invoiced**.

Free readout (no system access, nothing written to ERP):

1. You send two exports (below)  
2. We return customers with sold vs invoiced gaps and $ leakage  
3. Suggestions / flags only — **no invoices or credits created**

If the gaps matter, we can pilot **resolve** with human review (not another dashboard seat).

Reply with the two CSVs + company name.

Thanks,  
{You}

---

## 3. What they provide

| File | Source | Contents |
| --- | --- | --- |
| **Closed-won / sold** | HubSpot/Salesforce export | `customer_id`, `sold` (or amount), optional `company_name`, `deal_id` |
| **Invoices** | ERP AR | `invoice_id`, `customer_id`, `amount`, `status` |

`customer_id` must align across both files (ERP id or agreed mapping).

Templates: `data/ar_feed/templates/closed_won_template.csv` + `invoices_template.csv`  
Samples: `data/ar_feed/crm_closed_won.csv` + `erp_open_ar.csv`

---

## 4. What you send back

Markdown report:

- Total sold vs invoiced  
- Gap customers ranked by leakage $  
- Flags: `sold_vs_invoiced`, `sold_without_invoices`, `open_ar_over_sold`, etc.  
- CTA: free visibility; resolve is paid/pilot  

---

## 5. Ops (internal)

```bash
PYTHONPATH=. python scripts/free_leakage_report.py \
  --closed-won closed_won.csv \
  --invoices invoices.csv \
  --company "Their Co" \
  --out /tmp/leakage.md

# Cloud Run (after deploy)
curl -s -X POST https://finance-ops-301858971164.us-central1.run.app/v1/ar/free_leakage \
  -F "closed_won_csv=@closed_won.csv" \
  -F "invoices_csv=@invoices.csv" \
  -F "company_name=Their Co" | jq -r .markdown
```

---

## 6. Free vs paid

| Free | Paid / pilot |
| --- | --- |
| See leakage by customer | Create/chase invoice or credit with HITL |
| Two CSV readout | Ops SLA / retainer on hard gaps |
| No ERP writes | Metered resolve (not seats) |

---

## Why this wedge

- CFO-native: “are we billing what we sold?”  
- Data ask is CRM + AR — not remittance ops  
- Same product pattern as cash-app free visibility; different O2C pain  
