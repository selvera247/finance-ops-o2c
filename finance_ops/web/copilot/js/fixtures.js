/**
 * Story fixtures for /copilot/examples — edge cases without live API.
 * @module fixtures
 */

/** @type {import('./types.js').CaseSummary[]} */
export const FIXTURE_QUEUE = [
  {
    case_id: "cash_app:PAY-1001",
    payment_id: "PAY-1001",
    customer_id: "C-1042",
    amount: 2490,
    currency: "USD",
    status: "open",
    aging_days: 4,
    match_score: 0.91,
    confidence_band: "high",
  },
  {
    case_id: "cash_app:PAY-THIN",
    payment_id: "PAY-THIN",
    customer_id: "C-2099",
    amount: 180.5,
    currency: "USD",
    status: "need_info",
    aging_days: 12,
    match_score: 0.22,
    confidence_band: "insufficient",
  },
];

/** @type {import('./types.js').CaseDetail} */
export const FIXTURE_CASE_READY = {
  case_id: "cash_app:PAY-1001",
  payment_id: "PAY-1001",
  customer_id: "C-1042",
  amount: 2490,
  currency: "USD",
  status: "open",
  aging_days: 4,
  match_score: 0.91,
  hypothesis: {
    case_id: "cash_app:PAY-1001",
    payment_id: "PAY-1001",
    customer_id: "C-1042",
    lines: [{ invoice_id: "INV-84219", amount: 2490, rationale: "Exact amount + remittance ref" }],
    citation_map: [
      {
        source_id: "PAY-1001",
        source_type: "payment",
        claim: "Payment amount 2490",
      },
      {
        source_id: "REM-PAY-1001",
        source_type: "remittance",
        claim: "Invoice INV-84219 referenced",
      },
      {
        source_id: "INV-84219",
        source_type: "invoice",
        claim: "Open balance matches",
      },
    ],
    confidence_band: "high",
    insufficient_data: false,
    raw_notes: "Rules matched INV-84219 at full amount.",
  },
  summary: {
    case_id: "cash_app:PAY-1001",
    summary: "Remittance and open invoice agree on INV-84219 for USD 2,490.",
    confidence_band: "high",
  },
};

/** @type {import('./types.js').CaseDetail} */
export const FIXTURE_CASE_ABSTAIN = {
  case_id: "cash_app:PAY-THIN",
  payment_id: "PAY-THIN",
  customer_id: "C-2099",
  amount: 180.5,
  currency: "USD",
  status: "open",
  hypothesis: {
    case_id: "cash_app:PAY-THIN",
    payment_id: "PAY-THIN",
    lines: [],
    citation_map: [
      { source_id: "REM-SCAN-THIN", source_type: "remittance", claim: "OCR confidence low" },
    ],
    confidence_band: "insufficient",
    insufficient_data: true,
    raw_notes: "Thin remittance — abstain.",
  },
  summary: {
    case_id: "cash_app:PAY-THIN",
    summary: "Evidence too thin to propose a confident match.",
    confidence_band: "insufficient",
  },
};

/** @type {import('./types.js').EvidenceItem[]} */
export const FIXTURE_EVIDENCE = [
  {
    source_id: "PAY-1001",
    source_type: "payment",
    label: "Payment PAY-1001",
    fields: {
      payment_id: "PAY-1001",
      customer_id: "C-1042",
      amount: 2490,
      currency: "USD",
      reference: "INV-84219 / remittance PDF",
      status: "unmatched",
    },
  },
  {
    source_id: "REM-PAY-1001",
    source_type: "remittance",
    label: "Remittance REM-PAY-1001",
    fields: {
      method: "pdf_text",
      confidence: 0.94,
      invoice_ids: ["INV-84219"],
      text: "Please apply PAY-1001 to INV-84219 for USD 2,490. Thanks — AP desk.",
      extracted_fields: { invoice_ids: ["INV-84219"], raw_reference: "INV-84219" },
    },
  },
  {
    source_id: "INV-84219",
    source_type: "invoice",
    label: "Invoice INV-84219",
    fields: {
      invoice_id: "INV-84219",
      open_amount: 2490,
      amount: 2490,
      po_number: "PO-5510",
      status: "open",
      customer_id: "C-1042",
      currency: "USD",
    },
  },
  {
    source_id: "EML-4412",
    source_type: "email",
    label: "Email remittance thread",
    fields: {
      subject: "Re: PAY-1001 remittance",
      from_addr: "ap@customer.example",
      sent_at: "2026-11-03T18:22:00Z",
      snippet: "Attached remittance for PAY-1001 → INV-84219.",
      payment_refs: ["PAY-1001"],
      invoice_refs: ["INV-84219"],
    },
  },
];

/** @type {import('./types.js').EvidenceItem[]} */
export const FIXTURE_EVIDENCE_THIN = [
  {
    source_id: "REM-SCAN-THIN",
    source_type: "remittance",
    label: "Scanned remittance (thin)",
    fields: {
      method: "ocr",
      confidence: 0.21,
      thin_evidence: true,
      text: "…illegible scan…",
      invoice_ids: [],
    },
    stub: true,
  },
];

/** @type {import('./types.js').ApplyGuidancePacket} */
export const FIXTURE_GUIDANCE = {
  case_id: "cash_app:PAY-1001",
  payment_id: "PAY-1001",
  customer_id: "C-1042",
  invoice_ids: ["INV-84219"],
  lines: [{ invoice_id: "INV-84219", amount: 2490 }],
  total_amount: 2490,
  currency: "USD",
  actor: "workbench",
  decision: "accept",
  timestamp: "2026-11-04T00:00:00Z",
  copy_text: "GUIDANCE Apply PAY-1001 → INV-84219 USD 2490 (human ERP apply)",
  erp_deep_link_hint: "erp://cash-app/apply?payment=PAY-1001",
  warehouse_applied: false,
};

/** @type {import('./types.js').AuditEvent[]} */
export const FIXTURE_AUDIT = [
  {
    ts: "2026-11-04T00:00:01Z",
    event: "investigate",
    actor: "workbench",
    detail: { retriever_version: "copilot-evidence-v1" },
  },
  {
    ts: "2026-11-04T00:00:02Z",
    event: "hypothesis_drafted",
    actor: "system",
    detail: { confidence_band: "high", lines: 1 },
  },
  {
    ts: "2026-11-04T00:01:00Z",
    event: "decision",
    actor: "workbench",
    detail: { decision: "accept" },
  },
];

/** @type {import('./types.js').DigestPayload} */
export const FIXTURE_DIGEST_OFF = {
  enabled: false,
  status: "disabled",
  reason: "COPILOT_DIGEST_ENABLED is off (default) — avoid alert fatigue",
  items: [],
  excluded: [],
  gates: { min_confidence: "medium", exclude_insufficient: true, max_items: 20 },
};

/** Cross-customer deny style error for examples. */
export const FIXTURE_CROSS_CUSTOMER_ERROR =
  "cross_customer_denied: actor not scoped to customer C-9999";
