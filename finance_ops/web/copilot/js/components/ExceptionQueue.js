/**
 * Ranked exception queue with empty / loading / error states.
 * @module components/ExceptionQueue
 */

import { Component, el, formatMoney, setChildren } from "../utils.js";
import { Skeleton } from "./shared.js";

/**
 * @typedef {Object} ExceptionQueueProps
 * @property {import('../types.js').CaseSummary[]} [cases]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {string|null} [selectedId]
 * @property {boolean} [disabled]
 * @property {string} [ariaLabel]
 * @property {(caseId: string) => void} [onSelect]
 * @property {string} [emptyMessage]
 */

export class ExceptionQueue extends Component {
  render() {
    /** @type {ExceptionQueueProps} */
    const p = this.props;
    const label = p.ariaLabel || "Exception queue";

    if (p.loading) {
      const sk = el("div", {
        className: "cp-queue",
        role: "status",
        "aria-busy": "true",
        "aria-label": `${label} loading`,
        "data-state": "loading",
      });
      const mount = el("div");
      sk.append(mount);
      setChildren(this.root, sk);
      new Skeleton(mount, { rows: 4, block: true, ariaLabel: "Loading queue" }).render();
      return;
    }

    if (p.error) {
      setChildren(
        this.root,
        el(
          "div",
          {
            className: "cp-queue__error",
            role: "alert",
            "data-state": "error",
            "aria-label": label,
          },
          p.error,
        ),
      );
      return;
    }

    const cases = p.cases || [];
    if (!cases.length) {
      setChildren(
        this.root,
        el(
          "div",
          {
            className: "cp-queue__empty",
            role: "status",
            "data-state": "empty",
            "aria-label": label,
          },
          p.emptyMessage || "No cases. Sync the queue to load Spike A / warehouse exceptions.",
        ),
      );
      return;
    }

    const list = el(
      "div",
      {
        className: "cp-queue",
        role: "listbox",
        "aria-label": label,
        "data-state": "ready",
      },
      ...cases.map((c) => {
        const selected = c.case_id === p.selectedId;
        return el(
          "button",
          {
            type: "button",
            className: "cp-queue__item",
            role: "option",
            "aria-selected": selected ? "true" : "false",
            "aria-label": `Case ${c.case_id}, ${c.status || "open"}`,
            disabled: p.disabled,
            onClick: () => p.onSelect?.(c.case_id),
            onKeydown: (ev) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                p.onSelect?.(c.case_id);
              }
            },
          },
          el("div", { className: "cp-queue__id" }, c.case_id),
          el(
            "div",
            { className: "cp-queue__amt" },
            `${formatMoney(c.amount, c.currency || "USD")} · ${c.status || "open"}`,
          ),
          el(
            "div",
            { className: "cp-queue__meta" },
            `${c.payment_id || "—"} · aging ${c.aging_days ?? "?"}d · score ${c.match_score ?? "—"}`,
          ),
        );
      }),
    );
    setChildren(this.root, list);
  }
}
