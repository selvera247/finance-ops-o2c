/**
 * Case audit timeline — inputs → retrieval → draft → edits → decision.
 * Caps visible events; JSON detail lazy via collapsed Details.
 * @module components/AuditTimeline
 */

import { Component, el, jsonDetailsBlock, setChildren } from "../utils.js";
import { Skeleton } from "./shared.js";

const DEFAULT_VISIBLE = 20;

/**
 * @typedef {Object} AuditTimelineProps
 * @property {import('../types.js').AuditEvent[]} [events]
 * @property {string|null} [decisionActor]
 * @property {string|null} [decisionAt]
 * @property {string|null} [confidenceBand]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {string} [ariaLabel]
 * @property {number} [visibleCount]
 * @property {() => void} [onShowMore]
 */

export class AuditTimeline extends Component {
  render() {
    /** @type {AuditTimelineProps} */
    const p = this.props;
    const label = p.ariaLabel || "Audit timeline";

    if (p.loading) {
      const host = el("div", {
        "data-state": "loading",
        "aria-busy": "true",
        "aria-label": `${label} loading`,
      });
      setChildren(this.root, host);
      new Skeleton(host, { rows: 4, block: true }).render();
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

    const events = p.events || [];
    const meta = el(
      "p",
      { className: "copilot-muted" },
      `actor ${p.decisionActor || "—"} · at ${p.decisionAt || "—"} · confidence ${p.confidenceBand || "—"}`,
    );

    if (!events.length) {
      setChildren(
        this.root,
        el(
          "div",
          { "data-state": "empty", "aria-label": label },
          meta,
          el(
            "p",
            { className: "copilot-muted", role: "status" },
            "No audit events yet — Investigate or decide to append the trail.",
          ),
        ),
      );
      return;
    }

    // Show the most recent N events (audit is chronological).
    const visibleCap =
      p.visibleCount != null ? p.visibleCount : DEFAULT_VISIBLE;
    const start = Math.max(0, events.length - visibleCap);
    const slice = events.slice(start);

    const list = el(
      "ol",
      {
        className: "cp-audit",
        "aria-label": label,
        "data-state": "ready",
        start: start + 1,
      },
      ...slice.map((ev) =>
        el(
          "li",
          { className: "cp-audit__item" },
          el("div", { className: "cp-audit__ts" }, ev.ts || "—"),
          el(
            "div",
            { className: "cp-audit__event" },
            `${ev.event || "event"}${ev.actor ? ` · ${ev.actor}` : ""}`,
          ),
          ev.detail && Object.keys(ev.detail).length
            ? jsonDetailsBlock(ev.detail, {
                className: "cp-audit__detail",
                buttonLabel: "Event detail",
              })
            : null,
        ),
      ),
    );

    const nodes = [meta, list];
    if (start > 0) {
      nodes.push(
        el(
          "button",
          {
            type: "button",
            className: "cp-btn cp-btn--ghost cp-btn--sm",
            "aria-label": `Show older audit events (${start} hidden)`,
            onClick: () => p.onShowMore?.(),
          },
          `Show older (${start} hidden)`,
        ),
      );
    }

    setChildren(this.root, ...nodes);
  }
}
