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
