# Minimum viable discovery output format (OCFO)

**Owner:** Senior AI Deployment Manager, Finance  
**Audience:** Engagement lead → FDE / Enablement; also pattern library  
**Purpose:** One structured artifact per target workflow that is complete enough to scope an MVP, hand off, and measure—without a strategy deck.

**Assumptions**
- One primary workflow per discovery pack (e.g. cash-application exceptions, not “all of AR”).
- Discovery is 1–2 weeks of shadowing + artifacts + sample baselining, not interviews alone.
- Output is filled during discovery; blanks are explicit “unknown / gate” items, never invented.
- Human judgment remains on prioritization, control design, and material decisions.

**How to use**
1. Copy the skeleton below into the engagement folder (or Notion/Linear page).
2. Fill every section; mark `TBD — week-2 gate` where evidence is missing.
3. Attach raw notes/screenshots in an appendix; keep the body scannable.
4. Freeze a version at the go/revise gate; that version feeds the handoff package.

---

## 0. Header

| Field | Value |
| --- | --- |
| Client / BU | |
| Engagement ID | |
| Primary workflow | |
| Adjacent workflows (out of MVP) | |
| Discovery window | |
| Deployment Manager | |
| FDE / Enablement partner | |
| Pilot users (roles, n) | |
| Systems of record | |
| Document version / date | |
| Status | Draft · Gate-ready · Frozen for build |

**One-sentence problem statement**  
[Who fails at what, how often, with what cost or risk.]

**Recommended MVP wedge (if known)**  
[One sentence; else “pending assumption tests.”]

---

## 1. Process stages

Map the as-is path. Prefer what people *do*, not the SOP.

For each stage:

| Stage # | Name | Actor(s) | Trigger | Action today | Output / handoff | Tools used | Pain / delay |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |

**Happy path** (3–7 bullets)  
**Exception / rework loops** (where work returns or stalls)

**In scope for MVP stages**  
**Out of scope stages** (defer list with one-line why)

---

## 2. Systems and data

| System | Role (SoR / feed / collab) | Objects used | Access path today | Read needed? | Write needed in MVP? | Permission / ACL notes |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | No (default) | |

**Critical entities & join keys**  
e.g. customer_id, payment_id, invoice_id, remittance_id, amount, date, reference

**Data quality risks**  
Duplicates, missing remittance, free-text refs, cross-entity leakage, latency

**Artifacts reviewed** (bank files, PDFs, emails, screenshots—list with dates)

---

## 3. Controls and governance

| Control | Owner | When it applies | How enforced today | Must remain human? | AI implication |
| --- | --- | --- | --- | --- | --- |
| | | | | Y/N | |

**Materiality / approval thresholds**  
**Segregation of duties / audit requirements**  
**Non-negotiables for MVP** (e.g. no unattended ERP write-back)

---

## 4. Exceptions and failure modes

| Exception type | % of sample (or estimate) | How detected | Resolution path | Time to resolve | Candidate for AI assist? |
| --- | --- | --- | --- | --- | --- |
| | | | | | Propose / Draft / Route / Abstain |

**Top 3 failure modes that would kill trust**  
**Abstain / escalate rules** (when the system must not guess)

---

## 5. Volume and cycle time (baseline)

| Metric | Definition | Source | Window | Baseline value | Notes / confidence |
| --- | --- | --- | --- | --- | --- |
| Case volume | | | | | |
| Mix by type | | | | | |
| Touch time (min) | | | | | |
| Elapsed cycle time | | | | | |
| Rework rate | | | | | |
| Backlog / aging | | | | | |
| Direct labor $ (optional) | | | | | |

**Sample method**  
n=__, how selected, known bias  

**Directional annual labor** (if used in value case)  
Assumptions stated explicitly.

---

## 6. AI suitability

Score each candidate capability **H / M / L** with one-line evidence.

| Lens | Score | Evidence |
| --- | --- | --- |
| Data structured enough to retrieve / match | | |
| Ground truth available for eval (past labels) | | |
| Judgment risk if wrong | | |
| Feedback speed (days vs weeks) | | |
| Upstream of other workflows? | | |
| Permissioned retrieval feasible | | |
| Clear human gate possible | | |

**Recommended AI pattern mix**  
- Conventional software:  
- Retrieval / RAG:  
- Bounded agentic:  
- Generative (cited only):  
- Fine-tune: defer / yes because __  

**Explicitly not using** (e.g. unbounded web search, auto-post to ERP)

---

## 7. Success metrics and measurement contract

**Primary outcome** (one sentence)

| Layer | Metric | Baseline | Target (pilot) | How measured | Owner |
| --- | --- | --- | --- | --- | --- |
| AI quality | | | | | |
| User value | | | | | |
| Business impact | | | | | |

**Scale / revise / stop** (thresholds agreed with sponsor by end of discovery)

| Decision | If we observe… |
| --- | --- |
| Scale | |
| Revise | |
| Stop | |

**Assumptions still open at gate**  
1.  
2.  
3.  

---

## 8. Risks, dependencies, open questions

| Item | Type (risk / dep / Q) | Impact | Mitigation / owner | Needed by |
| --- | --- | --- | --- | --- |
| | | | | |

---

## 9. Gate checklist (go / revise)

- [ ] Shadowing + artifact review complete (not interviews only)  
- [ ] Sections 1–7 filled or marked TBD with owner  
- [ ] Baseline sample method agreed  
- [ ] Security / data access path for pilot named  
- [ ] Human gates and non-negotiable controls written  
- [ ] Sponsor agrees scale/revise/stop language  
- [ ] MVP wedge chosen **or** revise trigger hit (e.g. volume mix wrong)

**Gate decision:** Go · Revise scope · Stop  
**Rationale:**  

---

## Appendix A — Raw discovery index

Links to recordings, case IDs sampled, file drops, ACL notes.

## Appendix B — Pattern tags (for later reuse)

`process:` `industry:` `erp:` `wedge:` `pattern:` (e.g. evidence-backed exception assist)

---

## Field guide (keep short)

| Section | Good enough | Overkill |
| --- | --- | --- |
| Process | Stage table + happy/exception paths | Full BPMN |
| Systems | SoR + join keys + read/write | Enterprise architecture map |
| Controls | Non-negotiables + human gates | Full SOX narrative |
| Exceptions | Top types + abstain rules | Exhaustive taxonomy |
| Volume | Sample baseline + confidence | Perfect cost model |
| AI suitability | Scores + pattern mix | Model bake-off |
| Metrics | 3 layers + decision rules | Full ROI model |

**Next artifacts after freeze**
- [Handoff package](./ocfo-handoff-package-template.md)
- [Value-capture checkpoint](./ocfo-value-capture-checkpoint.md) (freeze baseline = Checkpoint 0)
- Process kit if applicable (e.g. [cash-app exceptions](./ocfo-kit-cash-app-exceptions.md))
- Internal cadence: [ops mirror](./ocfo-internal-ops-mirror.md)
