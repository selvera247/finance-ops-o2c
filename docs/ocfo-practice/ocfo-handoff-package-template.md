# DM → FDE / Enablement handoff package (OCFO)

**Purpose:** Freeze what to build after discovery so FDE (custom) or Enablement (ChatGPT / Codex / Cowork) can execute without re-discovering.  
**Upstream:** Frozen [discovery output](./ocfo-discovery-output-format.md) (gate = Go).  
**Downstream:** [Value-capture checkpoint](./ocfo-value-capture-checkpoint.md) (baseline = Checkpoint 0 from discovery §7; post-launch = Checkpoint 1+).  
**Kits:** [Cash-app exceptions](./ocfo-kit-cash-app-exceptions.md) · [Internal ops mirror](./ocfo-internal-ops-mirror.md)

**Assumptions**
- One primary workflow per package.
- Default MVP control: **no unattended SoR write-back** unless explicitly in scope.
- Path A = custom build (FDE). Path B = enablement / GPT workspace. Choose one primary; note hybrids.

---

## 0. Cover

| Field | Value |
| --- | --- |
| Client / BU | |
| Engagement ID | |
| Package version / date | |
| Deployment Manager | |
| Build path | FDE · Enablement · Hybrid |
| Primary engineer / enablement lead | |
| Discovery doc (link + version) | |
| Sponsor / pilot lead | |
| Target go-live window | |
| Status | Draft · Ready for build · Accepted by build |

**One-sentence outcome**  
[User can __ with __ evidence under __ human gate.]

---

## 1. Target workflow

**Name**  
**As-is stages in MVP** (IDs from discovery §1)  
**Users / roles in pilot** (n, locations, shift)  
**Systems in path** (read vs write)

**User journey (MVP)**  
1. Trigger →  
2. Assist surface →  
3. Human decision →  
4. Downstream action (manual / guided / system) →  

**Schema / contract sketch** (if custom)  
- Evidence in:  
- Hypothesis / draft out:  
- Apply / guidance packet (if any):  
- Audit events:  

---

## 2. In scope / out of scope

### In scope (MVP)
- 
- 

### Out of scope (explicit)
| Item | Why deferred |
| --- | --- |
| Unattended ERP write-back | Control default |
| | |

### Non-goals
- 

---

## 3. Acceptance criteria

Writable, testable. Prefer Given / When / Then or checklist.

| ID | Criterion | How verified | Owner |
| --- | --- | --- | --- |
| AC-1 | | | |
| AC-2 | Citations required on every recommendation | Eval / UI review | |
| AC-3 | Abstain when evidence insufficient | Fixture + pilot cases | |
| AC-4 | Human Accept / Edit / Reject (or equivalent) before post | Walkthrough | |
| AC-5 | Audit log of suggestion + human action | Spot check | |

**AI quality bar (pilot)**  
- Top-match / draft quality:  
- Abstention precision:  
- Forbidden failure: misread ID reaches apply without review  

**UX bar**  
- Pilot users can complete happy path without DM present  
- Reason codes available on reject / need-info  

---

## 4. Human gates and controls

| Gate | Who | When | Allowed AI action | Forbidden |
| --- | --- | --- | --- | --- |
| Review match / draft | AR / AP / Close owner | Before post | Propose, cite, abstain | Silent auto-post |
| | | | | |

**Materiality / dual control**  
**Permission model** (inherit ERP/mailbox ACL; no cross-customer leak)  
**Data retention / export rules for pilot**

---

## 5. Definition of done (build)

Done means all of:

- [ ] Acceptance criteria AC-* pass on agreed fixture + pilot sample  
- [ ] Eval harness or checklist runnable by DM without engineer  
- [ ] Human gates enforced in product or SOP (named)  
- [ ] Audit trail reviewable  
- [ ] Pilot runbook (1 page): how to use, when to escalate  
- [ ] Known limitations listed  
- [ ] Security / access for pilot signed off  
- [ ] Baseline metrics copied into value-capture sheet  
- [ ] Handoff accepted (sign-off below)

**Not done:** demos on synthetic data only with no pilot path, or “model works” without gates.

---

## 6. Baseline metrics (copy from discovery §7)

| Layer | Metric | Baseline | Pilot target | Measurement method |
| --- | --- | --- | --- | --- |
| AI quality | | | | |
| User value | | | | |
| Business impact | | | | |

**Scale / revise / stop** (from discovery; do not renegotiate silently)

---

## 7. Delivery slice

| Week / milestone | Outcome | Demo to users? |
| --- | --- | --- |
| Thin slice | End-to-end on sample | Y |
| Pilot harden | Failure modes fixed | Y |
| Measure | Checkpoint #1 | — |

**Technical risks to burn first**  
1.  
2.  

**Dependencies** (access, golden set labels, SME time)

---

## 8. Path-specific addenda

### A — FDE (custom)
- Repo / env:  
- Interfaces / APIs:  
- Fixtures / golden set location:  
- Observability:  

### B — Enablement (ChatGPT / Codex / Cowork)
- Workspace / GPT / project name:  
- Allowed tools / connectors:  
- Prompt + policy pack version:  
- What must stay human-verified:  

---

## 9. Sign-off

| Role | Name | Date | Notes |
| --- | --- | --- | --- |
| Deployment Manager | | | Package complete |
| FDE / Enablement | | | Accepted for build |
| Sponsor (optional) | | | Scope acknowledged |

---

## Field guide

| Section | Good enough | Overkill |
| --- | --- | --- |
| Target workflow | Journey + contract sketch | Full PRD |
| Scope | Bullets + defer table | Multi-quarter roadmap |
| Acceptance | 5–10 testable ACs | 50 edge cases |
| Gates | Table + ACL note | Full policy manual |
| DoD | Checklist above | Separate PMO plan |

**Pattern tags:** `handoff` `ocfo` `fde` `enablement` + process slug
