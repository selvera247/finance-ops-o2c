/**
 * Evidence pane — items grouped by source type, citation jump targets.
 * Human-readable summary first; raw JSON behind a Details toggle.
 * @module components/EvidencePane
 */

import {
  Component,
  el,
  evidenceSummaryFields,
  jsonDetailsBlock,
  renderSummaryList,
  setChildren,
} from "../utils.js";
import { Skeleton, StatusPill } from "./shared.js";

const SOURCE_ORDER = ["payment", "remittance", "invoice", "rule_match", "email"];

const DEFAULT_VISIBLE = 20;

/**
 * @typedef {Object} EvidencePaneProps
 * @property {import('../types.js').EvidenceItem[]} [items]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {boolean} [thinEvidence]
 * @property {string} [ariaLabel]
 * @property {(sourceId: string) => void} [onItemFocus]
 * @property {number} [visibleCount]
 * @property {() => void} [onShowMore]
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
      new Skeleton(host, { rows: 3, pulse: true }).render();
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

    const allItems = p.items || [];
    if (!allItems.length) {
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

    const visibleCap =
      p.visibleCount != null ? p.visibleCount : DEFAULT_VISIBLE;
    const items = allItems.slice(0, visibleCap);
    const hidden = Math.max(0, allItems.length - items.length);

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
      allItems.length < 2 ||
      allItems.every((it) => it.stub);

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
        const fields = it.fields || {};
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
        const summary = renderSummaryList(
          evidenceSummaryFields(it.source_type, fields, it.source_id),
          "cp-summary cp-evidence__summary",
        );
        if (summary) itemEl.append(summary);
        itemEl.append(
          jsonDetailsBlock(fields, {
            className: "cp-evidence__details",
            buttonLabel: "Details",
          }),
        );
        itemEl.addEventListener("focus", () => p.onItemFocus?.(it.source_id));
        group.append(itemEl);
      }
      root.append(group);
    }

    if (hidden > 0) {
      root.append(
        el(
          "button",
          {
            type: "button",
            className: "cp-btn cp-btn--ghost cp-btn--sm",
            "aria-label": `Show more evidence (${hidden} remaining)`,
            onClick: () => p.onShowMore?.(),
          },
          `Show more (${hidden} remaining)`,
        ),
      );
    }

    setChildren(this.root, root);
  }
}
