/**
 * DOM smoke test: EvidencePane / GuidancePacketView summary + Details toggle.
 * Run: node tests/js/evidence_display.test.mjs
 */
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COPILOT_JS = path.resolve(__dirname, "../../finance_ops/web/copilot/js");

/** Minimal DOM enough for Copilot `el` / Component render paths. */
class MiniNode {
  constructor() {
    this.childNodes = [];
    this.parentNode = null;
  }
  get textContent() {
    return this.childNodes.map((c) => c.textContent ?? "").join("");
  }
  set textContent(v) {
    this.childNodes = [];
    if (v != null && String(v) !== "") {
      this.childNodes.push(new MiniText(String(v)));
    }
  }
  append(...nodes) {
    for (const n of nodes) {
      const node = typeof n === "string" ? new MiniText(n) : n;
      if (node.parentNode) {
        node.parentNode.childNodes = node.parentNode.childNodes.filter((c) => c !== node);
      }
      node.parentNode = this;
      this.childNodes.push(node);
    }
  }
  appendChild(n) {
    this.append(n);
    return n;
  }
  replaceChildren(...nodes) {
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes = [];
    this.append(...nodes);
  }
}

class MiniText extends MiniNode {
  constructor(data) {
    super();
    this.nodeType = 3;
    this.data = String(data);
  }
  get textContent() {
    return this.data;
  }
  set textContent(v) {
    this.data = String(v ?? "");
  }
}

class MiniElement extends MiniNode {
  constructor(tagName) {
    super();
    this.nodeType = 1;
    this.tagName = String(tagName).toUpperCase();
    this.attributes = new Map();
    this.className = "";
    this.id = "";
    this.dataset = {};
    this.style = "";
    this._listeners = new Map();
    this.classList = {
      _set: new Set(),
      add: (c) => {
        this.classList._set.add(c);
        this.className = [...this.classList._set].join(" ");
      },
      remove: (c) => {
        this.classList._set.delete(c);
        this.className = [...this.classList._set].join(" ");
      },
      contains: (c) => this.classList._set.has(c),
    };
  }

  setAttribute(name, value) {
    const v = value == null ? "" : String(value);
    this.attributes.set(name, v);
    if (name === "id") this.id = v;
    if (name === "class") this.className = v;
  }

  getAttribute(name) {
    if (name === "class" && !this.attributes.has("class")) return this.className || null;
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "id") this.id = "";
  }

  addEventListener(type, fn) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(fn);
  }

  click() {
    for (const fn of this._listeners.get("click") || []) fn({ target: this });
  }

  focus() {}
  scrollIntoView() {}

  matches(selector) {
    if (selector.startsWith(".")) return this.className.split(/\s+/).includes(selector.slice(1));
    if (selector.startsWith("#")) return this.id === selector.slice(1);
    if (selector.includes("[")) {
      const m = selector.match(/^(\w+)?\[([^=\]]+)(?:=["']?([^"'\]]+)["']?)?\]$/);
      if (!m) return false;
      const [, tag, attr, val] = m;
      if (tag && this.tagName !== tag.toUpperCase()) return false;
      if (val != null) return this.getAttribute(attr) === val;
      return this.hasAttribute(attr) || (attr === "hidden" && this.attributes.has("hidden"));
    }
    return this.tagName === selector.toUpperCase();
  }

  querySelector(selector) {
    const all = this.querySelectorAll(selector);
    return all[0] || null;
  }

  querySelectorAll(selector) {
    const out = [];
    const walk = (node) => {
      if (node.nodeType === 1) {
        if (node.matches(selector)) out.push(node);
        for (const c of node.childNodes) walk(c);
      }
    };
    for (const c of this.childNodes) walk(c);
    return out;
  }

  get textContent() {
    return this.childNodes.map((c) => c.textContent ?? "").join("");
  }

  set textContent(v) {
    this.childNodes = [];
    if (v != null && String(v) !== "") this.childNodes.push(new MiniText(String(v)));
  }
}

const document = {
  body: new MiniElement("body"),
  createElement: (tag) => new MiniElement(tag),
  createTextNode: (t) => new MiniText(t),
  getElementById: () => null,
  querySelector: (sel) => document.body.querySelector(sel),
  querySelectorAll: (sel) => document.body.querySelectorAll(sel),
};

globalThis.document = document;
globalThis.window = globalThis;
globalThis.CSS = { escape: (s) => s.replace(/"/g, '\\"') };

const { EvidencePane } = await import(
  pathToFileURL(path.join(COPILOT_JS, "components/EvidencePane.js")).href
);
const { GuidancePacketView } = await import(
  pathToFileURL(path.join(COPILOT_JS, "components/GuidancePacketView.js")).href
);
const { formatJsonForDisplay, evidenceSummaryFields } = await import(
  pathToFileURL(path.join(COPILOT_JS, "utils.js")).href
);

const paymentFields = {
  payment_id: "PAY-9003",
  customer_id: "C-1042",
  amount: 1200,
  currency: "USD",
  reference: "INV-1",
  status: "unmatched",
};

{
  const pretty = formatJsonForDisplay(paymentFields);
  assert.equal(pretty.includes("&quot;"), false);
  assert.equal(pretty.includes('"payment_id"'), true);
  assert.equal(pretty.includes("\n  "), true);
}

{
  const rows = evidenceSummaryFields("payment", paymentFields, "PAY-9003");
  assert.ok(rows.some((r) => r.label === "Payment ID" && r.value === "PAY-9003"));
  assert.ok(rows.some((r) => r.label === "Customer" && r.value === "C-1042"));
}

{
  const root = document.createElement("div");
  new EvidencePane(root, {
    items: [
      {
        source_id: "PAY-9003",
        source_type: "payment",
        label: "Payment PAY-9003",
        fields: paymentFields,
      },
    ],
  }).render();

  const text = root.textContent;
  assert.equal(text.includes("&quot;"), false, "rendered evidence must not show HTML entities");
  assert.ok(text.includes("Payment ID"), "summary label Payment ID visible");
  assert.ok(text.includes("PAY-9003"), "payment id visible");
  assert.ok(text.includes("Customer"), "summary label Customer visible");
  assert.ok(text.includes("Amount"), "summary label Amount visible");

  const toggle = root.querySelector(".cp-json-details__toggle");
  assert.ok(toggle, "Details toggle present");
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.equal(toggle.textContent, "Details");

  const pre = root.querySelector(".cp-json-details__pre");
  assert.ok(pre, "JSON pre present");
  assert.ok(pre.hasAttribute("hidden"), "details collapsed by default");
  assert.equal(pre.textContent.includes("&quot;"), false);
  assert.ok(pre.textContent.includes('"payment_id"'));
  assert.ok(pre.textContent.includes('"PAY-9003"'));

  toggle.click();
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(pre.hasAttribute("hidden"), false);
}

{
  const root = document.createElement("div");
  new GuidancePacketView(root, {
    guidance: {
      case_id: "cash_app:PAY-9003",
      payment_id: "PAY-9003",
      customer_id: "C-1042",
      invoice_ids: ["INV-1"],
      total_amount: 1200,
      currency: "USD",
      decision: "accept",
      actor: "workbench",
      copy_text: "APPLY PAY-9003",
      warehouse_applied: false,
    },
  }).render();

  const text = root.textContent;
  assert.equal(text.includes("&quot;"), false);
  assert.ok(text.includes("Payment ID"));
  assert.ok(text.includes("PAY-9003"));
  assert.ok(text.includes("Invoices"));

  const toggle = root.querySelector(".cp-json-details__toggle");
  assert.ok(toggle);
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  const pre = root.querySelector(".cp-json-details__pre");
  assert.ok(pre.hasAttribute("hidden"));
  assert.equal(pre.textContent.includes("&quot;"), false);
  assert.ok(pre.textContent.includes('"payment_id"'));
}

console.log("evidence_display.test.mjs: ok");
