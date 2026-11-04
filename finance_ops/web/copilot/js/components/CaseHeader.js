/**
 * Case identity + status pills.
 * @module components/CaseHeader
 */

import { Component, el, formatMoney, isInsufficient, setChildren } from "../utils.js";
import { StatusPill } from "./shared.js";

/**
 * @typedef {Object} CaseHeaderProps
 * @property {import('../types.js').CaseDetail|null} [caseData]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {string} [ariaLabel]
 */

export class CaseHeader extends Component {
  render() {
    /** @type {CaseHeaderProps} */
    const p = this.props;
    const c = p.caseData;

    if (p.loading) {
      setChildren(
        this.root,
        el("div", {
          role: "status",
          "aria-busy": "true",
          "aria-label": p.ariaLabel || "Loading case",
          "data-state": "loading",
          className: "copilot-muted",
          text: "Loading case…",
        }),
      );
      return;
    }

    if (p.error) {
      setChildren(
        this.root,
        el("div", {
          role: "alert",
          "data-state": "error",
          className: "cp-banner cp-banner--danger",
          text: p.error,
        }),
      );
      return;
    }

    if (!c) {
      setChildren(
        this.root,
        el("div", {
          className: "copilot-muted",
          "data-state": "empty",
          role: "status",
          text: "Select a case from the queue.",
        }),
      );
      return;
    }

    const hyp = c.hypothesis || {};
    const insuff = isInsufficient(hyp);
    const title = el("div", { className: "cp-case-header__title" });
    title.append(
      el("span", { className: "cp-case-header__id" }, c.case_id),
    );
    const statusHost = el("span");
    title.append(statusHost);
    new StatusPill(statusHost, { status: c.status || "open" }).render();
    if (insuff) {
      const insuffHost = el("span");
      title.append(insuffHost);
      new StatusPill(insuffHost, {
        status: "insufficient",
        ariaLabel: "Insufficient data",
      }).render();
    }
    if (hyp.confidence_band && hyp.confidence_band !== "insufficient") {
      const bandHost = el("span");
      title.append(bandHost);
      new StatusPill(bandHost, {
        status: hyp.confidence_band,
        ariaLabel: `Confidence ${hyp.confidence_band}`,
      }).render();
    }

    setChildren(
      this.root,
      el(
        "header",
        {
          className: "cp-case-header",
          "data-state": "ready",
          "aria-label": p.ariaLabel || `Case ${c.case_id}`,
        },
        title,
        el(
          "p",
          { className: "copilot-muted" },
          `${c.payment_id || "—"} · ${c.customer_id || "—"} · ${formatMoney(c.amount, c.currency || "USD")}`,
        ),
        c.reason_code
          ? el(
              "p",
              { className: "copilot-muted" },
              `Last reason: ${c.reason_code} · decision ${c.last_decision || "—"}`,
            )
          : null,
      ),
    );
  }
}
