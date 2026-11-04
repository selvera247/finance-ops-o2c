/**
 * Shared primitives: Button, TextInput, TextArea, Select, Banner, Spinner, Skeleton, Modal.
 * @module components/shared
 */

import { Component, el, setChildren } from "../utils.js";

/**
 * @typedef {Object} ButtonProps
 * @property {string} [label]
 * @property {"primary"|"secondary"|"danger"|"warn"|"ghost"} [variant]
 * @property {"md"|"sm"} [size]
 * @property {boolean} [disabled]
 * @property {boolean} [loading]
 * @property {string} [ariaLabel]
 * @property {string} [type]
 * @property {(ev: MouseEvent) => void} [onClick]
 * @property {string} [className]
 */

export class Button extends Component {
  render() {
    /** @type {ButtonProps} */
    const p = this.props;
    const variant = p.variant || "primary";
    const size = p.size || "md";
    const classes = [
      "cp-btn",
      variant !== "primary" ? `cp-btn--${variant}` : "",
      size === "sm" ? "cp-btn--sm" : "",
      p.className || "",
    ]
      .filter(Boolean)
      .join(" ");

    const btn = el(
      "button",
      {
        type: p.type || "button",
        className: classes,
        disabled: Boolean(p.disabled || p.loading),
        "aria-label": p.ariaLabel || undefined,
        "aria-busy": p.loading ? "true" : undefined,
        onClick: (ev) => {
          if (p.disabled || p.loading) return;
          p.onClick?.(ev);
        },
      },
      p.loading ? el("span", { className: "cp-spinner", "aria-hidden": "true" }, "") : null,
      p.loading ? " " : null,
      p.label || "",
    );
    setChildren(this.root, btn);
  }
}

/**
 * @typedef {Object} TextFieldProps
 * @property {string} [id]
 * @property {string} [label]
 * @property {string} [value]
 * @property {string} [placeholder]
 * @property {boolean} [disabled]
 * @property {boolean} [required]
 * @property {string|null} [error]
 * @property {string} [hint]
 * @property {string} [ariaLabel]
 * @property {string} [name]
 * @property {string} [autocomplete]
 * @property {(value: string, ev: Event) => void} [onChange]
 * @property {number} [rows]
 */

function fieldWrap(p, control) {
  const classes = ["cp-field", p.error ? "cp-field--error" : ""].filter(Boolean).join(" ");
  return el(
    "div",
    { className: classes },
    p.label
      ? el("label", { className: "cp-field__label", for: p.id || undefined }, p.label)
      : null,
    control,
    p.error ? el("div", { className: "cp-field__error", role: "alert" }, p.error) : null,
    !p.error && p.hint ? el("div", { className: "cp-field__hint" }, p.hint) : null,
  );
}

export class TextInput extends Component {
  render() {
    /** @type {TextFieldProps} */
    const p = this.props;
    const input = el("input", {
      id: p.id,
      name: p.name,
      className: "cp-input",
      type: "text",
      value: p.value ?? "",
      placeholder: p.placeholder,
      disabled: p.disabled,
      required: p.required,
      autocomplete: p.autocomplete,
      "aria-label": p.ariaLabel || p.label,
      "aria-invalid": p.error ? "true" : undefined,
      onInput: (ev) => p.onChange?.(ev.target.value, ev),
    });
    // Preserve typed value (setAttribute doesn't update .value after mount).
    /** @type {HTMLInputElement} */ (input).value = p.value ?? "";
    setChildren(this.root, fieldWrap(p, input));
  }
}

export class TextArea extends Component {
  render() {
    /** @type {TextFieldProps} */
    const p = this.props;
    const ta = el("textarea", {
      id: p.id,
      name: p.name,
      className: "cp-textarea",
      placeholder: p.placeholder,
      disabled: p.disabled,
      required: p.required,
      rows: p.rows || 4,
      "aria-label": p.ariaLabel || p.label,
      "aria-invalid": p.error ? "true" : undefined,
      onInput: (ev) => p.onChange?.(ev.target.value, ev),
    });
    /** @type {HTMLTextAreaElement} */ (ta).value = p.value ?? "";
    setChildren(this.root, fieldWrap(p, ta));
  }
}

/**
 * @typedef {Object} SelectProps
 * @property {string} [id]
 * @property {string} [label]
 * @property {string} [value]
 * @property {{value: string, label: string}[]} [options]
 * @property {boolean} [disabled]
 * @property {boolean} [required]
 * @property {string|null} [error]
 * @property {string} [hint]
 * @property {string} [ariaLabel]
 * @property {string} [name]
 * @property {(value: string, ev: Event) => void} [onChange]
 */

export class Select extends Component {
  render() {
    /** @type {SelectProps} */
    const p = this.props;
    const select = el(
      "select",
      {
        id: p.id,
        name: p.name,
        className: "cp-select",
        disabled: p.disabled,
        required: p.required,
        "aria-label": p.ariaLabel || p.label,
        "aria-invalid": p.error ? "true" : undefined,
        onChange: (ev) => p.onChange?.(ev.target.value, ev),
      },
      ...(p.options || []).map((opt) =>
        el(
          "option",
          { value: opt.value, selected: opt.value === p.value },
          opt.label,
        ),
      ),
    );
    /** @type {HTMLSelectElement} */ (select).value = p.value ?? (p.options?.[0]?.value || "");
    setChildren(this.root, fieldWrap(p, select));
  }
}

/**
 * @typedef {Object} BannerProps
 * @property {"info"|"success"|"warn"|"danger"} [variant]
 * @property {string} [title]
 * @property {string} [message]
 * @property {boolean} [live]
 * @property {string} [role]
 */

export class Banner extends Component {
  render() {
    /** @type {BannerProps} */
    const p = this.props;
    const variant = p.variant || "info";
    const node = el(
      "div",
      {
        className: `cp-banner cp-banner--${variant}`,
        role: p.role || (variant === "danger" || variant === "warn" ? "alert" : "status"),
        "aria-live": p.live === false ? undefined : "polite",
      },
      p.title ? el("span", { className: "cp-banner__title" }, p.title) : null,
      p.message || "",
    );
    setChildren(this.root, node);
  }
}

/**
 * @typedef {Object} SpinnerProps
 * @property {"md"|"lg"} [size]
 * @property {string} [ariaLabel]
 * @property {boolean} [labelVisible]
 */

export class Spinner extends Component {
  render() {
    /** @type {SpinnerProps} */
    const p = this.props;
    const label = p.ariaLabel || "Loading";
    setChildren(
      this.root,
      el(
        "span",
        {
          className: `cp-spinner${p.size === "lg" ? " cp-spinner--lg" : ""}`,
          role: "status",
          "aria-label": label,
        },
        el("span", { className: "copilot-sr-only" }, label),
      ),
    );
  }
}

/**
 * @typedef {Object} SkeletonProps
 * @property {number} [rows]
 * @property {boolean} [block]
 * @property {string} [ariaLabel]
 */

export class Skeleton extends Component {
  render() {
    /** @type {SkeletonProps} */
    const p = this.props;
    const rows = p.rows ?? 3;
    const items = [];
    for (let i = 0; i < rows; i += 1) {
      items.push(
        el("div", {
          className: `cp-skeleton${p.block ? " cp-skeleton--block" : ""}`,
          style: p.block ? undefined : `width:${70 + ((i * 13) % 30)}%`,
        }),
      );
    }
    setChildren(
      this.root,
      el(
        "div",
        {
          className: "cp-skeleton-group",
          role: "status",
          "aria-busy": "true",
          "aria-label": p.ariaLabel || "Loading content",
        },
        ...items,
      ),
    );
  }
}

/**
 * @typedef {Object} ModalProps
 * @property {boolean} [open]
 * @property {string} [title]
 * @property {string} [message]
 * @property {string} [confirmLabel]
 * @property {string} [cancelLabel]
 * @property {"primary"|"danger"|"warn"} [confirmVariant]
 * @property {boolean} [disabled]
 * @property {() => void} [onConfirm]
 * @property {() => void} [onCancel]
 * @property {string} [ariaLabel]
 */

export class Modal extends Component {
  render() {
    /** @type {ModalProps} */
    const p = this.props;
    if (!p.open) {
      setChildren(this.root);
      return;
    }

    const titleId = `${p.id || "cp-modal"}-title`;
    const onKey = (ev) => {
      if (ev.key === "Escape" && !p.disabled) {
        ev.stopPropagation();
        p.onCancel?.();
      }
    };

    const backdrop = el(
      "div",
      {
        className: "cp-modal-backdrop",
        role: "presentation",
        onClick: (ev) => {
          if (ev.target === backdrop && !p.disabled) p.onCancel?.();
        },
        onKeydown: onKey,
      },
      el(
        "div",
        {
          className: "cp-modal",
          role: "dialog",
          "aria-modal": "true",
          "aria-labelledby": titleId,
          "aria-label": p.ariaLabel,
          tabindex: "-1",
        },
        el("h2", { id: titleId }, p.title || "Confirm"),
        el("p", { className: "copilot-muted" }, p.message || ""),
        el(
          "div",
          { className: "cp-modal__actions" },
          el(
            "button",
            {
              type: "button",
              className: "cp-btn cp-btn--ghost",
              disabled: p.disabled,
              onClick: () => p.onCancel?.(),
            },
            p.cancelLabel || "Cancel",
          ),
          el(
            "button",
            {
              type: "button",
              className: `cp-btn${p.confirmVariant && p.confirmVariant !== "primary" ? ` cp-btn--${p.confirmVariant}` : ""}`,
              disabled: p.disabled,
              onClick: () => p.onConfirm?.(),
            },
            p.confirmLabel || "Confirm",
          ),
        ),
      ),
    );

    setChildren(this.root, backdrop);
    const dialog = backdrop.querySelector(".cp-modal");
    /** @type {HTMLElement|null} */ (dialog)?.focus();
  }
}

/**
 * @typedef {Object} StatusPillProps
 * @property {string} [status]
 * @property {string} [ariaLabel]
 */

export class StatusPill extends Component {
  render() {
    /** @type {StatusPillProps} */
    const p = this.props;
    const status = (p.status || "unknown").toLowerCase();
    const safe = status.replace(/[^a-z0-9_]/g, "_");
    setChildren(
      this.root,
      el(
        "span",
        {
          className: `cp-status-pill cp-status-pill--${safe}`,
          "aria-label": p.ariaLabel || `Status ${status}`,
        },
        status,
      ),
    );
  }
}
