/**
 * Case audit timeline — inputs → retrieval → draft → edits → decision.
 * @module components/AuditTimeline
 */

import { Component, el, esc, setChildren } from "../utils.js";
import { Skeleton } from "./shared.js";

/**
 * @typedef {Object} AuditTimelineProps
 * @property {import('../types.js').AuditEvent[]} [events]
 * @property {string|null} [decisionActor]
 * @property {string|null} [decisionAt]
 * @property {string|null} [confidenceBand]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {string} [ariaLabel]
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

    const list = el(
      "ol",
      {
        className: "cp-audit",
        "aria-label": label,
        "data-state": "ready",
      },
      ...events.map((ev) =>
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
            ? el(
                "pre",
                { className: "cp-audit__detail" },
                esc(JSON.stringify(ev.detail, null, 2)),
              )
            : null,
        ),
      ),
    );

    setChildren(this.root, meta, list);
  }
}
