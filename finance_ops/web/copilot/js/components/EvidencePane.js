/**
 * Evidence pane — items grouped by source type, citation jump targets.
 * @module components/EvidencePane
 */

import { Component, el, esc, setChildren } from "../utils.js";
import { Skeleton, StatusPill } from "./shared.js";

const SOURCE_ORDER = ["payment", "remittance", "invoice", "rule_match", "email"];

/**
 * @typedef {Object} EvidencePaneProps
 * @property {import('../types.js').EvidenceItem[]} [items]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {boolean} [thinEvidence]
 * @property {string} [ariaLabel]
 * @property {(sourceId: string) => void} [onItemFocus]
 */

/**
 * Scroll/highlight an evidence item by source id (citation click-through).
 * @param {string} sourceId
 * @param {ParentNode} [scope]
 * @returns {boolean}
 */
export function jumpToEvidence(sourceId, scope = document) {
  const safe = typeof CSS !== "undefined" && CSS.escape
    ? CSS.escape(sourceId)
    : sourceId.replace(/"/g, '\\"');
  const node = scope.querySelector(`#ev-${safe}`);
  if (!node) return false;
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  node.classList.add("is-flash");
  window.setTimeout(() => node.classList.remove("is-flash"), 1200);
  if (typeof node.focus === "function") {
    try {
      node.focus({ preventScroll: true });
    } catch {
      node.focus();
    }
  }
  return true;
}

export class EvidencePane extends Component {
  render() {
    /** @type {EvidencePaneProps} */
    const p = this.props;
    const label = p.ariaLabel || "Evidence";

    if (p.loading) {
      const host = el("div", {
        "data-state": "loading",
        "aria-busy": "true",
        "aria-label": `${label} loading`,
      });
      setChildren(this.root, host);
      new Skeleton(host, { rows: 3, block: true }).render();
      return;
    }

    if (p.error) {
      setChildren(
        this.root,
        el("div", {
          className: "cp-banner cp-banner--danger",
          role: "alert",
          "data-state": "error",
          text: p.error,
        }),
      );
      return;
    }

    const items = p.items || [];
    if (!items.length) {
      setChildren(
        this.root,
        el(
          "div",
          {
            className: "copilot-muted",
            role: "status",
            "data-state": "empty",
            "aria-label": label,
          },
          "No evidence yet — run Investigate to retrieve payment, remittance, and invoice sources.",
        ),
      );
      return;
    }

    const groups = new Map();
    for (const item of items) {
      const key = item.source_type || "other";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    const keys = [
      ...SOURCE_ORDER.filter((k) => groups.has(k)),
      ...[...groups.keys()].filter((k) => !SOURCE_ORDER.includes(k)),
    ];

    const thin =
      p.thinEvidence ||
      items.length < 2 ||
      items.every((it) => it.stub);

    const root = el("div", {
      className: "cp-evidence",
      "data-state": thin ? "thin" : "ready",
      "aria-label": label,
    });

    if (thin) {
      root.append(
        el(
          "div",
          {
            className: "cp-banner cp-banner--warn",
            role: "status",
            style: "margin-bottom:0.75rem",
          },
          el("span", { className: "cp-banner__title" }, "Thin evidence"),
          "Retrieved pack is sparse or stubbed — prefer Need info / Escalate over confident Accept.",
        ),
      );
    }

    for (const key of keys) {
      const group = el("section", {
        className: "cp-evidence__group",
        "aria-label": `${key} evidence`,
      });
      group.append(el("h3", { className: "cp-evidence__group-title" }, key));
      for (const it of groups.get(key)) {
        const itemEl = el(
          "article",
          {
            className: "cp-evidence__item",
            id: `ev-${it.source_id}`,
            tabindex: "-1",
            "data-source-id": it.source_id,
            "data-source-type": it.source_type,
            "aria-label": `${it.source_type} ${it.source_id}`,
          },
          el("div", { className: "cp-evidence__label" }, it.label || it.source_id),
          el(
            "div",
            { className: "cp-evidence__sid" },
            `${it.source_type} · ${it.source_id}`,
          ),
        );
        if (it.stub) {
          const pillHost = el("div", { style: "margin-top:0.35rem" });
          itemEl.append(pillHost);
          new StatusPill(pillHost, { status: "stub", ariaLabel: "Stub evidence" }).render();
        }
        itemEl.append(
          el(
            "pre",
            { className: "cp-evidence__fields" },
            esc(JSON.stringify(it.fields || {}, null, 2)),
          ),
        );
        itemEl.addEventListener("focus", () => p.onItemFocus?.(it.source_id));
        group.append(itemEl);
      }
      root.append(group);
    }

    setChildren(this.root, root);
  }
}
