/**
 * Shared DOM / a11y helpers for Copilot components.
 * @module utils
 */

/**
 * Escape text for safe HTML interpolation.
 * @param {unknown} value
 * @returns {string}
 */
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c],
  );
}

/**
 * Pretty-print a JSON-ish payload for textContent display (never HTML-escape).
 * Objects/arrays → 2-space JSON; JSON-looking strings are parsed first.
 * @param {unknown} value
 * @returns {string}
 */
export function formatJsonForDisplay(value) {
  if (value == null) return "";
  let payload = value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        payload = JSON.parse(trimmed);
      } catch {
        return value;
      }
    } else {
      return value;
    }
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(value);
  }
}

let _jsonDetailsSeq = 0;

/**
 * @param {unknown} value
 * @returns {string}
 */
function summaryDisplayValue(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map(String).join(", ") : "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

/**
 * @param {unknown} text
 * @param {number} [max]
 * @returns {string}
 */
function shortenText(text, max = 140) {
  const s = String(text ?? "");
  if (!s) return "—";
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

/**
 * Labeled summary rows for an evidence item (demo-readable; not raw JSON).
 * @param {string} sourceType
 * @param {Record<string, unknown>} [fields]
 * @param {string} [sourceId]
 * @returns {{label: string, value: string}[]}
 */
export function evidenceSummaryFields(sourceType, fields = {}, sourceId = "") {
  const f = fields && typeof fields === "object" && !Array.isArray(fields) ? fields : {};
  /** @param {...string} keys */
  const pick = (...keys) => {
    for (const k of keys) {
      if (f[k] != null && f[k] !== "") return f[k];
    }
    return null;
  };
  const currency = /** @type {string} */ (pick("currency") || "USD");
  const money = (amt) => (amt == null || amt === "" ? "—" : formatMoney(amt, currency));

  if (sourceType === "payment") {
    return [
      { label: "Payment ID", value: summaryDisplayValue(pick("payment_id") || sourceId) },
      { label: "Customer", value: summaryDisplayValue(pick("customer_id")) },
      { label: "Amount", value: money(pick("amount")) },
      { label: "Currency", value: summaryDisplayValue(pick("currency")) },
      { label: "Reference", value: summaryDisplayValue(pick("reference")) },
      { label: "Status", value: summaryDisplayValue(pick("status")) },
    ];
  }

  if (sourceType === "invoice") {
    return [
      { label: "Invoice ID", value: summaryDisplayValue(pick("invoice_id") || sourceId) },
      { label: "Amount", value: money(pick("amount", "open_amount")) },
      { label: "PO", value: summaryDisplayValue(pick("po_number", "po")) },
      { label: "Status", value: summaryDisplayValue(pick("status")) },
      { label: "Customer", value: summaryDisplayValue(pick("customer_id")) },
      { label: "Currency", value: summaryDisplayValue(pick("currency")) },
    ];
  }

  if (sourceType === "remittance") {
    const extracted =
      f.extracted_fields && typeof f.extracted_fields === "object"
        ? /** @type {Record<string, unknown>} */ (f.extracted_fields)
        : {};
    const invIds = pick("invoice_ids") ?? extracted.invoice_ids;
    const conf = pick("confidence");
    let confLabel = "—";
    if (conf != null && conf !== "") {
      const n = Number(conf);
      confLabel = !Number.isNaN(n) && n <= 1 ? `${Math.round(n * 100)}%` : String(conf);
    }
    return [
      { label: "Method", value: summaryDisplayValue(pick("method")) },
      { label: "Confidence", value: confLabel },
      { label: "Invoice IDs", value: summaryDisplayValue(invIds) },
      { label: "Text", value: shortenText(pick("text", "notes")) },
    ];
  }

  if (sourceType === "email") {
    return [
      { label: "Subject", value: summaryDisplayValue(pick("subject")) },
      { label: "From", value: summaryDisplayValue(pick("from_addr", "from")) },
      { label: "Sent", value: summaryDisplayValue(pick("sent_at")) },
      { label: "Snippet", value: shortenText(pick("snippet", "body_preview")) },
      { label: "Payment refs", value: summaryDisplayValue(pick("payment_refs")) },
      { label: "Invoice refs", value: summaryDisplayValue(pick("invoice_refs")) },
    ];
  }

  // rule_match / other — surface a few useful scalars without dumping JSON.
  const preferred = ["invoice_id", "score", "confidence", "customer_id", "amount", "reasons"];
  const rows = [];
  for (const key of preferred) {
    if (f[key] == null || f[key] === "") continue;
    const label = key
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
    rows.push({
      label,
      value:
        key === "amount"
          ? money(f[key])
          : summaryDisplayValue(f[key]),
    });
  }
  if (!rows.length && sourceId) {
    rows.push({ label: "Source ID", value: sourceId });
  }
  return rows;
}

/**
 * Labeled summary rows for an ApplyGuidancePacket.
 * @param {Record<string, unknown>} g
 * @returns {{label: string, value: string}[]}
 */
export function guidanceSummaryFields(g = {}) {
  const currency = /** @type {string} */ (g.currency || "USD");
  return [
    { label: "Payment ID", value: summaryDisplayValue(g.payment_id) },
    { label: "Customer", value: summaryDisplayValue(g.customer_id) },
    { label: "Invoices", value: summaryDisplayValue(g.invoice_ids) },
    {
      label: "Total",
      value:
        g.total_amount == null || g.total_amount === ""
          ? "—"
          : formatMoney(g.total_amount, currency),
    },
    { label: "Currency", value: summaryDisplayValue(g.currency) },
    { label: "Decision", value: summaryDisplayValue(g.decision) },
    { label: "Actor", value: summaryDisplayValue(g.actor) },
  ];
}

/**
 * Render a labeled definition list for summary rows.
 * @param {{label: string, value: string}[]} rows
 * @param {string} [className]
 * @returns {HTMLElement|null}
 */
export function renderSummaryList(rows, className = "cp-summary") {
  if (!rows || !rows.length) return null;
  return el(
    "dl",
    { className },
    ...rows.map((row) =>
      el(
        "div",
        { className: "cp-summary__row" },
        el("dt", { className: "cp-summary__label" }, row.label),
        el("dd", { className: "cp-summary__value" }, row.value),
      ),
    ),
  );
}

/**
 * Collapsed-by-default Details toggle for pretty-printed JSON (textContent, real quotes).
 * @param {unknown} payload
 * @param {{ className?: string, buttonLabel?: string, hideLabel?: string }} [opts]
 * @returns {HTMLElement}
 */
export function jsonDetailsBlock(payload, opts = {}) {
  const id = `cp-json-details-${++_jsonDetailsSeq}`;
  const showLabel = opts.buttonLabel || "Details";
  const hideLabel = opts.hideLabel || "Hide details";
  const pre = el("pre", {
    id,
    className: "cp-json-details__pre",
    hidden: true,
    text: formatJsonForDisplay(payload),
  });
  const btn = el(
    "button",
    {
      type: "button",
      className: "cp-btn cp-btn--ghost cp-btn--sm cp-json-details__toggle",
      "aria-expanded": "false",
      "aria-controls": id,
      onClick: () => {
        const open = btn.getAttribute("aria-expanded") === "true";
        const next = !open;
        btn.setAttribute("aria-expanded", next ? "true" : "false");
        if (next) pre.removeAttribute("hidden");
        else pre.setAttribute("hidden", "");
        btn.textContent = next ? hideLabel : showLabel;
      },
    },
    showLabel,
  );
  return el(
    "div",
    { className: ["cp-json-details", opts.className].filter(Boolean).join(" ") },
    btn,
    pre,
  );
}

/**
 * @param {unknown} amount
 * @param {string} [currency]
 * @returns {string}
 */
export function formatMoney(amount, currency = "USD") {
  if (amount == null || amount === "") return "—";
  const n = Number(amount);
  if (Number.isNaN(n)) return `${currency} ${amount}`;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "USD",
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

/**
 * Announce a message to screen readers via an aria-live region.
 * @param {string} message
 * @param {"polite"|"assertive"} [priority]
 */
export function announce(message, priority = "polite") {
  let live = document.getElementById("copilot-live");
  if (!live) {
    live = document.createElement("div");
    live.id = "copilot-live";
    live.className = "copilot-live";
    live.setAttribute("aria-live", priority);
    live.setAttribute("aria-atomic", "true");
    document.body.appendChild(live);
  } else {
    live.setAttribute("aria-live", priority);
  }
  live.textContent = "";
  // Force a DOM change so SR re-announces identical strings.
  window.setTimeout(() => {
    live.textContent = message;
  }, 30);
}

/**
 * Clear a root and append children.
 * @param {HTMLElement} root
 * @param {...(Node|string|null|undefined|false)} nodes
 */
export function setChildren(root, ...nodes) {
  root.replaceChildren();
  for (const n of nodes) {
    if (n == null || n === false) continue;
    root.append(typeof n === "string" ? document.createTextNode(n) : n);
  }
}

/**
 * Create an element with optional attrs/children.
 * @param {string} tag
 * @param {Record<string, unknown>} [attrs]
 * @param {...(Node|string|null|undefined|false)} children
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs || {})) {
    if (val == null || val === false) continue;
    if (key === "className") {
      node.className = String(val);
    } else if (key === "text") {
      node.textContent = String(val);
    } else if (key === "html") {
      node.innerHTML = String(val);
    } else if (key.startsWith("on") && typeof val === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), val);
    } else if (key === "dataset" && typeof val === "object") {
      Object.assign(node.dataset, val);
    } else if (typeof val === "boolean") {
      if (val) node.setAttribute(key, "");
    } else {
      node.setAttribute(key, String(val));
    }
  }
  for (const child of children) {
    if (child == null || child === false) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

/**
 * Shallow equality for skip-render (functions compared by reference).
 * @param {Record<string, unknown>} a
 * @param {Record<string, unknown>} b
 */
export function shallowEqualProps(a, b) {
  if (a === b) return true;
  const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
  for (const k of keys) {
    if ((a || {})[k] !== (b || {})[k]) return false;
  }
  return true;
}

/**
 * Stable component base: holds props, re-renders into a root.
 */
export class Component {
  /**
   * @param {HTMLElement} root
   * @param {Record<string, unknown>} [props]
   */
  constructor(root, props = {}) {
    if (!root) throw new Error("Component requires a root element");
    this.root = root;
    this.props = { ...props };
    this._bound = false;
  }

  /**
   * @param {Record<string, unknown>} [next]
   * @param {{ force?: boolean }} [opts]
   */
  update(next = {}, opts = {}) {
    const merged = { ...this.props, ...next };
    if (!opts.force && shallowEqualProps(this.props, merged)) {
      return;
    }
    this.props = merged;
    this.render();
  }

  /** @returns {void} */
  render() {
    throw new Error("render() not implemented");
  }
}

/**
 * @param {() => void} fn
 * @param {number} ms
 */
export function debounce(fn, ms) {
  let t = 0;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => {
      t = 0;
      fn(...args);
    }, ms);
  };
}

/**
 * Reason-code catalogs aligned with `finance_ops/copilot/reasons.py`.
 */
export const REASON_CODES = {
  reject: [
    { value: "reject_wrong_customer", label: "Wrong customer" },
    { value: "reject_duplicate", label: "Duplicate" },
    { value: "reject_not_our_payment", label: "Not our payment" },
    { value: "reject_other", label: "Other" },
  ],
  escalate: [
    { value: "escalate_materiality", label: "Materiality" },
    { value: "escalate_ambiguous", label: "Ambiguous" },
    { value: "escalate_policy", label: "Policy" },
    { value: "escalate_other", label: "Other" },
  ],
  need_info: [
    { value: "need_info_remittance", label: "Need remittance" },
    { value: "need_info_email", label: "Need email" },
    { value: "need_info_invoice", label: "Need invoice" },
    { value: "need_info_other", label: "Other" },
  ],
};

/**
 * @param {import('./types.js').MatchHypothesis|null|undefined} hyp
 * @returns {boolean}
 */
export function isInsufficient(hyp) {
  if (!hyp) return false;
  return Boolean(hyp.insufficient_data) || hyp.confidence_band === "insufficient";
}
