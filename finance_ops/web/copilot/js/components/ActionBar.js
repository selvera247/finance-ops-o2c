/**
 * Decision action bar: Accept | Edit&ready | Reject | Escalate | Need-info.
 * @module components/ActionBar
 */

import { Component, el, REASON_CODES, setChildren } from "../utils.js";
import { Button, Modal, Select } from "./shared.js";

/**
 * @typedef {Object} ActionBarProps
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {boolean} [disabled]
 * @property {boolean} [acceptDisabled] - e.g. insufficient data
 * @property {boolean} [investigating]
 * @property {string} [ariaLabel]
 * @property {string} [rejectReason]
 * @property {string} [escalateReason]
 * @property {string} [needInfoReason]
 * @property {(decision: string, reasonCode: string|null) => void} [onDecision]
 * @property {() => void} [onInvestigate]
 * @property {(kind: "reject"|"escalate"|"need_info", value: string) => void} [onReasonChange]
 */

export class ActionBar extends Component {
  constructor(root, props = {}) {
    super(root, props);
    this._confirm = null;
  }

  /**
   * @param {string} decision
   * @param {string|null} reason
   * @param {string} title
   * @param {string} message
   * @param {"primary"|"danger"|"warn"} [variant]
   */
  _askConfirm(decision, reason, title, message, variant = "primary") {
    this._confirm = { decision, reason, title, message, variant };
    this.render();
  }

  _clearConfirm() {
    this._confirm = null;
    this.render();
  }

  render() {
    /** @type {ActionBarProps} */
    const p = this.props;
    const busy = Boolean(p.disabled || p.loading);

    const root = el("div", {
      className: "cp-action-bar",
      role: "group",
      "aria-label": p.ariaLabel || "Case actions",
      "data-state": p.loading ? "loading" : p.error ? "error" : "ready",
    });

    if (p.error) {
      root.append(
        el("div", {
          className: "cp-banner cp-banner--danger",
          role: "alert",
          text: p.error,
        }),
      );
    }

    const primary = el("div", { className: "cp-action-bar__primary" });
    const invHost = el("span");
    const acceptHost = el("span");
    const editHost = el("span");
    primary.append(invHost, acceptHost, editHost);
    root.append(primary);

    new Button(invHost, {
      label: p.investigating ? "Investigating…" : "Investigate",
      loading: p.investigating,
      disabled: busy,
      ariaLabel: "Run investigate",
      onClick: () => p.onInvestigate?.(),
    }).render();

    new Button(acceptHost, {
      label: "Accept",
      variant: "secondary",
      disabled: busy || p.acceptDisabled,
      ariaLabel: p.acceptDisabled
        ? "Accept disabled due to insufficient data"
        : "Accept hypothesis and emit guidance packet",
      onClick: () =>
        this._askConfirm(
          "accept",
          null,
          "Accept hypothesis?",
          "Emits an ApplyGuidancePacket for ERP copy/deep-link. Does not post cash.",
          "primary",
        ),
    }).render();

    new Button(editHost, {
      label: "Edit & ready",
      variant: "secondary",
      disabled: busy,
      ariaLabel: "Edit and mark ready to apply",
      onClick: () =>
        this._askConfirm(
          "edit_ready_to_apply",
          null,
          "Mark ready to apply?",
          "Saves current hypothesis edits and emits ApplyGuidancePacket. Warehouse apply stays off unless demo flag is set.",
          "primary",
        ),
    }).render();

    const gated = el("div", { className: "cp-action-bar__gated" });

    const rejectBtn = el("span");
    const rejectSel = el("span", { className: "cp-action-bar__reason" });
    const escBtn = el("span");
    const escSel = el("span", { className: "cp-action-bar__reason" });
    const needBtn = el("span");
    const needSel = el("span", { className: "cp-action-bar__reason" });
    gated.append(rejectBtn, rejectSel, escBtn, escSel, needBtn, needSel);
    root.append(gated);

    const rejectReason = p.rejectReason || REASON_CODES.reject[0].value;
    const escalateReason = p.escalateReason || REASON_CODES.escalate[0].value;
    const needInfoReason = p.needInfoReason || REASON_CODES.need_info[0].value;

    new Button(rejectBtn, {
      label: "Reject",
      variant: "danger",
      disabled: busy,
      onClick: () =>
        this._askConfirm(
          "reject",
          rejectReason,
          "Reject case?",
          `Reason: ${rejectReason}`,
          "danger",
        ),
    }).render();
    new Select(rejectSel, {
      id: "reason-reject",
      label: "Reject reason",
      options: REASON_CODES.reject,
      value: rejectReason,
      disabled: busy,
      ariaLabel: "Reject reason code",
      onChange: (v) => p.onReasonChange?.("reject", v),
    }).render();

    new Button(escBtn, {
      label: "Escalate",
      variant: "warn",
      disabled: busy,
      onClick: () =>
        this._askConfirm(
          "escalate",
          escalateReason,
          "Escalate case?",
          `Reason: ${escalateReason}`,
          "warn",
        ),
    }).render();
    new Select(escSel, {
      id: "reason-escalate",
      label: "Escalate reason",
      options: REASON_CODES.escalate,
      value: escalateReason,
      disabled: busy,
      ariaLabel: "Escalate reason code",
      onChange: (v) => p.onReasonChange?.("escalate", v),
    }).render();

    new Button(needBtn, {
      label: "Need info",
      variant: "warn",
      disabled: busy,
      onClick: () =>
        this._askConfirm(
          "need_info",
          needInfoReason,
          "Request more info?",
          `Reason: ${needInfoReason}`,
          "warn",
        ),
    }).render();
    new Select(needSel, {
      id: "reason-need_info",
      label: "Need-info reason",
      options: REASON_CODES.need_info,
      value: needInfoReason,
      disabled: busy,
      ariaLabel: "Need-info reason code",
      onChange: (v) => p.onReasonChange?.("need_info", v),
    }).render();

    const modalHost = el("div");
    root.append(modalHost);
    new Modal(modalHost, {
      open: Boolean(this._confirm),
      title: this._confirm?.title,
      message: this._confirm?.message,
      confirmVariant: this._confirm?.variant || "primary",
      confirmLabel: "Confirm",
      cancelLabel: "Cancel",
      disabled: busy,
      onCancel: () => this._clearConfirm(),
      onConfirm: () => {
        const c = this._confirm;
        this._confirm = null;
        if (c) p.onDecision?.(c.decision, c.reason);
        this.render();
      },
    }).render();

    setChildren(this.root, root);
  }
}
