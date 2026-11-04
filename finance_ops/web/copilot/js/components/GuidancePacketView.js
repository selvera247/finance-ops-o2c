/**
 * ApplyGuidancePacket display — guidance-only happy path.
 * @module components/GuidancePacketView
 */

import { Component, el, esc, setChildren } from "../utils.js";
import { Banner, Button } from "./shared.js";

/**
 * @typedef {Object} GuidancePacketViewProps
 * @property {import('../types.js').ApplyGuidancePacket|null} [guidance]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {string} [ariaLabel]
 */

export class GuidancePacketView extends Component {
  render() {
    /** @type {GuidancePacketViewProps} */
    const p = this.props;

    if (p.loading) {
      setChildren(
        this.root,
        el("div", {
          role: "status",
          "aria-busy": "true",
          "data-state": "loading",
          className: "copilot-muted",
          text: "Loading guidance…",
        }),
      );
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

    const g = p.guidance;
    if (!g) {
      setChildren(
        this.root,
        el(
          "div",
          {
            className: "copilot-muted",
            role: "status",
            "data-state": "empty",
            "aria-label": p.ariaLabel || "Apply guidance packet",
          },
          "No guidance yet — Accept or Edit & ready emits the ApplyGuidancePacket for ERP copy/deep-link.",
        ),
      );
      return;
    }

    const root = el("div", {
      className: "cp-guidance",
      "data-state": "ready",
      "aria-label": p.ariaLabel || "Apply guidance packet",
    });

    const bannerHost = el("div", { style: "margin-bottom:0.75rem" });
    root.append(bannerHost);
    new Banner(bannerHost, {
      variant: g.warehouse_applied ? "warn" : "success",
      title: g.warehouse_applied ? "Demo apply ran" : "Guidance only",
      message: g.warehouse_applied
        ? "Warehouse apply executed because FINANCE_OPS_DEMO_APPLY=1."
        : "Copy into current ERP. AI did not post cash.",
    }).render();

    if (g.copy_text) {
      root.append(el("h3", { className: "copilot-muted" }, "Copy text"));
      root.append(el("pre", { className: "cp-guidance__copy" }, g.copy_text));
      const btnHost = el("div", { className: "copilot-row", style: "margin:0.5rem 0 0.75rem" });
      root.append(btnHost);
      new Button(btnHost, {
        label: "Copy to clipboard",
        variant: "secondary",
        size: "sm",
        ariaLabel: "Copy guidance packet text",
        onClick: async () => {
          try {
            await navigator.clipboard.writeText(g.copy_text || "");
          } catch {
            /* ignore */
          }
        },
      }).render();
    }

    if (g.erp_deep_link_hint) {
      root.append(
        el("p", { className: "copilot-muted" }, `Deep-link hint: ${g.erp_deep_link_hint}`),
      );
    }

    root.append(el("h3", { className: "copilot-muted" }, "Packet JSON"));
    root.append(
      el("pre", { className: "cp-guidance__json" }, esc(JSON.stringify(g, null, 2))),
    );

    setChildren(this.root, root);
  }
}
