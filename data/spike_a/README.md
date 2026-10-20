# Spike A — cash app matching sample

Scrubbed exception-queue style payments + open AR for demo matching.

| File | Rows |
| --- | --- |
| `payments.csv` | 13 (unmatched / partial) |
| `invoices.csv` | 9 open/past_due |

**Must-fix applied:** `PAY-4001` reference is `Remittance INV-77110` (substring match on `invoice_id`).

## Load into DuckDB warehouse

```bash
PYTHONPATH=. python scripts/load_spike_a.py
# or refresh only these customers:
PYTHONPATH=. python scripts/load_spike_a.py --replace-customers
```

Then:

```bash
PYTHONPATH=. python -c "from finance_ops.tools.payment_tools import suggest_payment_match; import json; print(json.dumps(suggest_payment_match('PAY-1001'), indent=2))"
```

## Live walkthrough (3 payments)

| # | Payment | Story | Expect |
| --- | --- | --- | --- |
| 1 | **PAY-1001** | Clean remittance | Recommend **INV-84219** (INV id + amount); still `needs_review` |
| 2 | **PAY-2001** | Ambiguous amount | Candidates **INV-92001** and **INV-92004** (tolerance); HITL chooses |
| 3 | **PAY-3001** | Cash, no open AR | Customer **C-3329** has no invoices → empty candidates → escalate |

Optional encore: **PAY-4002** (clean PO hit → INV-77111), **PAY-1002** (weak PO / wrong amount).

## Agent prompts

```text
List unmatched payments for customer_id=C-1042 and cite evidence_id.
Suggest payment match for PAY-1001 and cite recommendation + evidence_id.
Suggest payment match for PAY-2001; explain why needs_review.
Suggest payment match for PAY-3001; request approval if no candidates.
```
