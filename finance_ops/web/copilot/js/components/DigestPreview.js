/**
 * Optional digest preview — messaging stays off-by-default.
 * @module components/DigestPreview
 */

import { Component, el, formatMoney, setChildren } from "../utils.js";
import { Banner, Skeleton } from "./shared.js";

/**
 * @typedef {Object} DigestPreviewProps
 * @property {import('../types.js').DigestPayload|null} [digest]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {boolean} [forceShown] - show dry-run even when disabled
 * @property {string} [ariaLabel]
 */

export class DigestPreview extends Component {
  render() {
    /** @type {DigestPreviewProps} */
    const p = this.props;
    const label = p.ariaLabel || "Digest preview";

    if (p.loading) {
      const host = el("div", {
        className: "cp-digest",
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

    const d = p.digest;
    if (!d) {
      setChildren(
        this.root,
        el(
          "div",
          {
            className: "cp-digest",
            "data-state": "empty",
            role: "status",
            "aria-label": label,
          },
          el(
            "p",
            { className: "cp-digest__off" },
            "Digest not loaded. Optional daily digest stays off by default to avoid alert fatigue.",
          ),
        ),
      );
      return;
    }

    const enabled = Boolean(d.enabled);
    const root = el("div", {
      className: "cp-digest",
      "data-state": enabled ? "ready" : "disabled",
      "aria-label": label,
    });

    const bannerHost = el("div", { style: "margin-bottom:0.75rem" });
    root.append(bannerHost);
    new Banner(bannerHost, {
      variant: enabled ? "info" : "warn",
      title: enabled ? "Digest enabled" : "Digest off by default",
      message:
        d.reason ||
        (enabled
          ? "Ranked exceptions that pass confidence gates."
          : "Set COPILOT_DIGEST_ENABLED=1 only after a pilot precision bar is agreed. Use force dry-run for preview."),
    }).render();

    const items = d.items || [];
    if (!items.length) {
      root.append(
        el(
          "p",
          { className: "cp-digest__off", role: "status" },
          enabled
            ? "No items passed digest quality gates."
            : "No digest items (disabled).",
        ),
      );
    } else {
      for (const it of items) {
        root.append(
          el(
            "div",
            { className: "cp-digest__item" },
            el("strong", { className: "copilot-mono" }, it.case_id || "—"),
            " · ",
            formatMoney(it.amount, it.currency || "USD"),
            " · ",
            it.confidence_band || it.status || "—",
          ),
        );
      }
    }

    if (d.excluded?.length) {
      root.append(
        el(
          "p",
          { className: "copilot-muted", style: "margin-top:0.75rem" },
          `${d.excluded.length} excluded by gates`,
        ),
      );
    }

    setChildren(this.root, root);
  }
}
