/**
 * Story-like examples page — each component in empty / loading / ready / error states.
 * Fixtures are lazy-imported so the examples shell paints before payload JSON loads.
 * @module examples
 */

import {
  ActionBar,
  AuditTimeline,
  Banner,
  Button,
  CaseHeader,
  DigestPreview,
  EvidencePane,
  ExceptionQueue,
  GuidancePacketView,
  HypothesisDraft,
  jumpToEvidence,
  Modal,
  Select,
  Skeleton,
  Spinner,
  StatusPill,
  TextArea,
  TextInput,
} from "./components/index.js";
import { el } from "./utils.js";

/**
 * @param {HTMLElement} root
 * @param {string} title
 * @param {string} blurb
 * @returns {HTMLElement}
 */
function section(root, title, blurb) {
  const sec = el("section", { "aria-labelledby": undefined });
  const h = el("h2", {}, title);
  h.id = `ex-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  sec.setAttribute("aria-labelledby", h.id);
  sec.append(h, el("p", { className: "copilot-muted" }, blurb));
  const grid = el("div", { className: "copilot-examples-grid" });
  sec.append(grid);
  root.append(sec);
  return grid;
}

/**
 * @param {HTMLElement} grid
 * @param {string} label
 * @returns {HTMLElement}
 */
function card(grid, label) {
  const panel = el("div", { className: "copilot-panel" });
  panel.append(el("h3", { className: "copilot-muted" }, label));
  const host = el("div");
  panel.append(host);
  grid.append(panel);
  return host;
}

function mountShared(root) {
  const grid = section(root, "Shared primitives", "Buttons, fields, banners, loading, modal.");

  const btnHost = card(grid, "Button variants");
  const row = el("div", { className: "copilot-row" });
  btnHost.append(row);
  ["primary", "secondary", "danger", "warn", "ghost"].forEach((variant) => {
    const h = el("span");
    row.append(h);
    new Button(h, { label: variant, variant, size: "sm" }).render();
  });
  const loadingBtn = el("span");
  row.append(loadingBtn);
  new Button(loadingBtn, { label: "Saving", loading: true, size: "sm" }).render();

  const fieldHost = card(grid, "TextInput / TextArea / Select");
  const f1 = el("div");
  const f2 = el("div", { style: "margin-top:0.5rem" });
  const f3 = el("div", { style: "margin-top:0.5rem" });
  fieldHost.append(f1, f2, f3);
  new TextInput(f1, { id: "ex-input", label: "Invoice", value: "INV-84219", ariaLabel: "Example invoice" }).render();
  new TextArea(f2, { id: "ex-area", label: "Notes", value: "Sample rationale", rows: 2 }).render();
  new Select(f3, {
    id: "ex-select",
    label: "Reason",
    options: [
      { value: "a", label: "Option A" },
      { value: "b", label: "Option B" },
    ],
    value: "a",
  }).render();

  const bannerHost = card(grid, "Banner / Alert");
  ["info", "success", "warn", "danger"].forEach((variant) => {
    const h = el("div", { style: "margin-bottom:0.5rem" });
    bannerHost.append(h);
    new Banner(h, {
      variant,
      title: variant,
      message: `Example ${variant} banner`,
    }).render();
  });

  const loadHost = card(grid, "Spinner / Skeleton");
  const sp = el("div", { className: "copilot-row", style: "margin-bottom:0.75rem" });
  const sk = el("div");
  loadHost.append(sp, sk);
  const spHost = el("span");
  sp.append(spHost);
  new Spinner(spHost, { ariaLabel: "Example spinner" }).render();
  new Skeleton(sk, { rows: 3, block: true }).render();

  const modalHost = card(grid, "Modal");
  const openBtn = el("span");
  const modalRoot = el("div");
  modalHost.append(openBtn, modalRoot);
  let open = false;
  const paintModal = () => {
    new Modal(modalRoot, {
      open,
      title: "Confirm example",
      message: "Escape closes. Backdrop click cancels.",
      onCancel: () => {
        open = false;
        paintModal();
      },
      onConfirm: () => {
        open = false;
        paintModal();
      },
    }).render();
  };
  new Button(openBtn, {
    label: "Open modal",
    variant: "secondary",
    onClick: () => {
      open = true;
      paintModal();
    },
  }).render();
  paintModal();

  const pillHost = card(grid, "StatusPill");
  const pills = el("div", { className: "copilot-row" });
  pillHost.append(pills);
  ["open", "ready_to_apply", "need_info", "escalated", "closed_rejected", "insufficient"].forEach(
    (status) => {
      const h = el("span");
      pills.append(h);
      new StatusPill(h, { status }).render();
    },
  );
}

function mountQueue(root) {
  const grid = section(
    root,
    "ExceptionQueue",
    "Ranked list with empty, loading, error, and ready states.",
  );
  const empty = card(grid, "empty");
  new ExceptionQueue(empty, { cases: [], loading: false }).render();
  const loading = card(grid, "loading");
  new ExceptionQueue(loading, { loading: true }).render();
  const error = card(grid, "error");
  new ExceptionQueue(error, { error: "Failed to load queue", loading: false }).render();
  const ready = card(grid, "ready");
  new ExceptionQueue(ready, {
    cases: FIXTURE_QUEUE,
    selectedId: FIXTURE_QUEUE[0].case_id,
    onSelect: () => {},
  }).render();
}

function mountCase(root) {
  const grid = section(root, "CaseHeader", "Identity + status / confidence pills.");
  const empty = card(grid, "empty");
  new CaseHeader(empty, { caseData: null }).render();
  const ready = card(grid, "ready");
  new CaseHeader(ready, { caseData: FIXTURE_CASE_READY }).render();
  const abstain = card(grid, "abstain / insufficient");
  new CaseHeader(abstain, { caseData: FIXTURE_CASE_ABSTAIN }).render();
  const denied = card(grid, "cross-customer deny");
  new CaseHeader(denied, { error: FIXTURE_CROSS_CUSTOMER_ERROR }).render();
}

function mountEvidence(root) {
  const grid = section(
    root,
    "EvidencePane",
    "Labeled summary fields first; raw JSON behind a collapsed Details toggle. Citation targets use #ev-{source_id}.",
  );
  const empty = card(grid, "empty");
  new EvidencePane(empty, { items: [] }).render();
  const thin = card(grid, "thin / stub");
  new EvidencePane(thin, { items: FIXTURE_EVIDENCE_THIN, thinEvidence: true }).render();
  const ready = card(grid, "ready + citation jump");
  new EvidencePane(ready, { items: FIXTURE_EVIDENCE }).render();
  const citeRow = el("div", { className: "copilot-row", style: "margin-top:0.5rem" });
  ready.append(citeRow);
  new Button(citeRow, {
    label: "Jump to REM-PAY-1001",
    variant: "secondary",
    size: "sm",
    onClick: () => jumpToEvidence("REM-PAY-1001", ready),
  }).render();
}

function mountHypothesis(root) {
  const grid = section(
    root,
    "HypothesisDraft",
    "Editable lines, citation chips, insufficient-data banner.",
  );
  const ready = card(grid, "editable ready");
  new HypothesisDraft(ready, {
    hypothesis: FIXTURE_CASE_READY.hypothesis,
    summary: FIXTURE_CASE_READY.summary,
    onCitationClick: (id) => jumpToEvidence(id, document),
  }).render();
  const insuff = card(grid, "insufficient / abstain");
  new HypothesisDraft(insuff, {
    hypothesis: FIXTURE_CASE_ABSTAIN.hypothesis,
    summary: FIXTURE_CASE_ABSTAIN.summary,
  }).render();
  const failed = card(grid, "failed investigate");
  new HypothesisDraft(failed, {
    error: "Investigate failed: remittance extractor timeout",
  }).render();
}

function mountActions(root) {
  const grid = section(
    root,
    "ActionBar",
    "Accept blocked on insufficient; reason codes on Reject / Escalate / Need-info.",
  );
  const ready = card(grid, "ready (Accept enabled)");
  new ActionBar(ready, {
    acceptDisabled: false,
    onInvestigate: () => {},
    onDecision: () => {},
  }).render();
  const blocked = card(grid, "insufficient (Accept disabled)");
  new ActionBar(blocked, {
    acceptDisabled: true,
    onInvestigate: () => {},
    onDecision: () => {},
  }).render();
}

function mountGuidance(root) {
  const grid = section(
    root,
    "GuidancePacketView",
    "Guidance-only packet after Accept / Edit & ready — summary fields first, packet JSON in Details.",
  );
  const empty = card(grid, "empty");
  new GuidancePacketView(empty, { guidance: null }).render();
  const ready = card(grid, "packet ready");
  new GuidancePacketView(ready, { guidance: FIXTURE_GUIDANCE }).render();
}

function mountAudit(root) {
  const grid = section(root, "AuditTimeline", "Chronological investigate → draft → decision.");
  const empty = card(grid, "empty");
  new AuditTimeline(empty, { events: [] }).render();
  const ready = card(grid, "ready");
  new AuditTimeline(ready, {
    events: FIXTURE_AUDIT,
    decisionActor: "workbench",
    decisionAt: "2026-11-04T00:01:00Z",
    confidenceBand: "high",
  }).render();
}

function mountDigest(root) {
  const grid = section(
    root,
    "DigestPreview",
    "Optional digest — messaging off by default until precision bar agreed.",
  );
  const off = card(grid, "off by default");
  new DigestPreview(off, { digest: FIXTURE_DIGEST_OFF }).render();
  const on = card(grid, "enabled preview");
  new DigestPreview(on, {
    digest: {
      enabled: true,
      status: "ok",
      items: FIXTURE_QUEUE.filter((c) => c.confidence_band !== "insufficient"),
      excluded: [{ case_id: "cash_app:PAY-THIN", reasons: ["insufficient_data"] }],
    },
  }).render();
}

async function main() {
  const root = document.getElementById("examples-root");
  if (!root) return;
  // Shared primitives need no fixtures — paint immediately.
  mountShared(root);
  const status = el("p", { className: "copilot-muted", role: "status" }, "Loading example fixtures…");
  root.append(status);
  // Defer fixture JSON until after first paint / idle.
  const fixtures = await import("./fixtures.js");
  ({
    FIXTURE_AUDIT,
    FIXTURE_CASE_ABSTAIN,
    FIXTURE_CASE_READY,
    FIXTURE_CROSS_CUSTOMER_ERROR,
    FIXTURE_DIGEST_OFF,
    FIXTURE_EVIDENCE,
    FIXTURE_EVIDENCE_THIN,
    FIXTURE_GUIDANCE,
    FIXTURE_QUEUE,
  } = fixtures);
  status.remove();
  mountQueue(root);
  mountCase(root);
  mountEvidence(root);
  mountHypothesis(root);
  mountActions(root);
  mountGuidance(root);
  mountAudit(root);
  mountDigest(root);
}

/** @type {any} */
let FIXTURE_AUDIT;
/** @type {any} */
let FIXTURE_CASE_ABSTAIN;
/** @type {any} */
let FIXTURE_CASE_READY;
/** @type {any} */
let FIXTURE_CROSS_CUSTOMER_ERROR;
/** @type {any} */
let FIXTURE_DIGEST_OFF;
/** @type {any} */
let FIXTURE_EVIDENCE;
/** @type {any} */
let FIXTURE_EVIDENCE_THIN;
/** @type {any} */
let FIXTURE_GUIDANCE;
/** @type {any} */
let FIXTURE_QUEUE;

main();
