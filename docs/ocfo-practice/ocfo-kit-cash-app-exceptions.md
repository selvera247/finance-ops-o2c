# Reusable kit — Cash-application exceptions

**Process slug:** `cash-app-exceptions`  
**Pattern:** Evidence-backed exception assist (propose + cite + human gate; no unattended ERP write by default)  
**Use when:** Unmatched / partially matched payments create AR exceptions; remittance + invoice evidence exists; pilot can keep human apply.

**Companion templates:** [Discovery](./ocfo-discovery-output-format.md) · [Handoff](./ocfo-handoff-package-template.md) · [Value capture](./ocfo-value-capture-checkpoint.md)  
**Reference build (optional):** `finance-ops-o2c` Cash-App Exception Copilot (workbench, evidence pack, ApplyGuidancePacket, eval)

---

## 1. Kit intent

| Item | Default |
| --- | --- |
| User | AR cash appliers / exception reviewers |
| Job | Investigate exception → accept / edit / reject / need-info with citations |
| MVP control | ERP **read-only**; guidance packet or existing manual post |
| Defer | Collections prioritization, dispute packets, broad alerts, auto write-back |

---

## 2. Discovery pre-fill (edit per client)

### Process stages (starter)
1. Payment lands unmatched / exception queue  
2. Gather remittance (email, PDF, lockbox, portal)  
3. Find candidate invoices  
4. Propose allocation  
5. Human confirm / adjust  
6. Post in ERP (manual / guided)  
7. Clear exception / audit  

### Join keys
`customer_id`, `payment_id`, `invoice_id`, `amount`, `date`, `reference` / remittance text

### Assumption tests (week 1–2)
| # | Assumption | Test |
| --- | --- | --- |
| 1 | Cash-app is large share of exception volume | Classify + time sample |
| 2 | Enough cases matchable from available evidence | Hand-match golden set |
| 3 | Remittance email/scan readable | Extraction spike |
| 4 | Reviewers trust cited proposals | 3–5 user walkthroughs |
| 5 | ERP read + permission pass-through | Security sign-off |

### AI suitability defaults
- Strong: structured payments/invoices, past matches as labels, human confirm, fast feedback  
- Watch: OCR quality, ACL inheritance, partial remittances → abstain  

### Metrics starter
| Layer | Examples |
| --- | --- |
| AI quality | Top-match accuracy; abstention precision; misread-ID rate to reviewer |
| User value | Min/case; accept vs edit vs reject; weekly active pilots |
| Business impact | Reviewer minutes saved; time-to-apply; exception aging |

---

## 3. Handoff pre-fill

**Outcome:** Pilot users clear matchable cash-app exceptions via cited recommendations under a human gate.

**In scope:** Queue, evidence pack (payment/remittance/invoice/email if permitted), ranked hypothesis with citations, abstain, Accept/Edit/Reject/Need-info, audit, guidance-only apply  

**Out of scope:** Unattended write-back, collections/disputes, SSO-or-prod mailbox unless contracted  

**Acceptance criteria (starter)**
- AC-1 Every recommendation has `citation_map` / source links  
- AC-2 Unknown invoice IDs cannot be proposed without validation against open invoices  
- AC-3 Thin/missing remittance → abstain or need-info, not a guess  
- AC-4 No ERP post without human Accept/Edit path  
- AC-5 Audit of investigate + decision  

**Schema contract**
1. Evidence pack in (`source_id`s)  
2. Hypothesis out (lines, confidence, `insufficient_data`, versions)  
3. ApplyGuidancePacket after human decision  

**Human gates:** AR reviewer before post; materiality / dual control per client policy  

---

## 4. Build path options

| Path | When | Notes |
| --- | --- | --- |
| FDE custom | Deep ERP integration, workbench UX, eval harness | Copilot-shaped product |
| Enablement | Fast GPT workspace over permitted exports / connectors | Same gates; weaker native audit unless designed |
| Hybrid | GPT for extract; FDE for queue + controls | Contract still required |

---

## 5. Fixtures & eval (minimum)

- Golden set: past human matches (payment → invoice lines) labeled  
- Thin remittance / missing email cases for abstain  
- Cross-customer negative case for ACL  
- Eval: top-match, abstain precision, forbidden misread-ID  

---

## 6. Pilot runbook (1-pager outline)

1. Sync / open queue  
2. Select case → Investigate  
3. Read evidence + hypothesis  
4. Accept / Edit / Reject / Need-info with reason  
5. Post via existing ERP process using guidance packet  
6. Escalate path if ACL or data gap  

---

## 7. Pattern extraction checklist (end of engagement)

- [ ] Discovery pack filled and tagged `cash-app-exceptions`  
- [ ] What was client-specific vs reusable noted  
- [ ] Failure modes added to kit § risk log  
- [ ] Metric defs that worked promoted to value-capture defaults  
- [ ] Screens / prompts / schema diffs filed for kit vN+1  

**Risk log (living)**

| Risk | Mitigation |
| --- | --- |
| Spike-A-only seed ≠ client mix | Discovery volume test |
| DuckDB/demo ≠ live ERP ACL | Access spike week 1–2 |
| Partial remittance overconfidence | Abstain + medium band |

---

## Field guide

Ship the kit as **defaults + edit marks**, not a fake completed discovery. Always re-run assumption tests.
