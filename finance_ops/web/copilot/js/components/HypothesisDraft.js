/**
 * Editable match hypothesis + summary with insufficient-data banner and citation chips.
 * @module components/HypothesisDraft
 */

import { Component, el, isInsufficient, setChildren } from "../utils.js";
import { Banner, Button, TextArea, TextInput } from "./shared.js";

/**
 * @typedef {Object} HypothesisDraftProps
 * @property {import('../types.js').MatchHypothesis|null} [hypothesis]
 * @property {import('../types.js').InvestigationSummary|null} [summary]
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {boolean} [disabled]
 * @property {boolean} [editable]
 * @property {string} [ariaLabel]
 * @property {(sourceId: string) => void} [onCitationClick]
 * @property {(next: { lines: import('../types.js').MatchLine[], raw_notes: string }) => void} [onChange]
 * @property {() => void} [onSave]
 */

export class HypothesisDraft extends Component {
  render() {
    /** @type {HypothesisDraftProps} */
    const p = this.props;
    const hyp = p.hypothesis || { lines: [], citation_map: [], confidence_band: "insufficient" };
    const lines = Array.isArray(hyp.lines) && hyp.lines.length
      ? hyp.lines.map((l) => ({ ...l }))
      : [{ invoice_id: "", amount: 0, rationale: "" }];
    const notes = hyp.raw_notes || "";
    const insufficient = isInsufficient(hyp);
    const editable = p.editable !== false;

    if (p.loading) {
      setChildren(
        this.root,
        el("div", {
          role: "status",
          "aria-busy": "true",
          "data-state": "loading",
          className: "copilot-muted",
          text: "Drafting hypothesis…",
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

    const root = el("div", {
      className: "cp-hypothesis",
      "data-state": insufficient ? "insufficient" : "ready",
      "aria-label": p.ariaLabel || "Match hypothesis",
    });

    if (insufficient) {
      const bannerHost = el("div", { style: "margin-bottom:0.75rem" });
      root.append(bannerHost);
      new Banner(bannerHost, {
        variant: "warn",
        title: "Insufficient data",
        message:
          "Confident Accept is blocked. Use Need info, Escalate, or edit lines after reviewing citations.",
        live: true,
      }).render();
    }

    const cites = hyp.citation_map || [];
    const citeRow = el("div", {
      className: "cp-hypothesis__cites",
      "aria-label": "Citations",
    });
    if (!cites.length) {
      citeRow.append(el("span", { className: "copilot-muted" }, "No citations"));
    } else {
      for (const c of cites) {
        citeRow.append(
          el(
            "a",
            {
              className: "cp-cite",
              href: `#ev-${c.source_id}`,
              title: c.claim || c.span || c.source_id,
              "aria-label": `Citation ${c.source_type} ${c.source_id}`,
              onClick: (ev) => {
                ev.preventDefault();
                p.onCitationClick?.(c.source_id);
              },
            },
            `${c.source_type}:${c.source_id}`,
          ),
        );
      }
    }
    root.append(citeRow);

    const linesHost = el("div", {
      className: "cp-hypothesis__lines",
      role: "group",
      "aria-label": "Match lines",
      style: "margin-top:0.75rem",
    });

    const emitChange = (nextLines, nextNotes) => {
      p.onChange?.({ lines: nextLines, raw_notes: nextNotes });
    };

    lines.forEach((line, idx) => {
      const row = el("div", { className: "cp-hyp-line" });
      const invHost = el("div");
      const amtHost = el("div");
      row.append(invHost, amtHost);
      new TextInput(invHost, {
        id: `hyp-inv-${idx}`,
        label: idx === 0 ? "Invoice ID" : undefined,
        value: line.invoice_id || "",
        disabled: p.disabled || !editable,
        ariaLabel: `Invoice ID line ${idx + 1}`,
        onChange: (v) => {
          const next = lines.map((l, i) =>
            i === idx ? { ...l, invoice_id: v } : l,
          );
          emitChange(next, notes);
        },
      }).render();
      new TextInput(amtHost, {
        id: `hyp-amt-${idx}`,
        label: idx === 0 ? "Amount" : undefined,
        value: line.amount != null ? String(line.amount) : "",
        disabled: p.disabled || !editable,
        ariaLabel: `Amount line ${idx + 1}`,
        onChange: (v) => {
          const next = lines.map((l, i) =>
            i === idx ? { ...l, amount: Number(v) || 0 } : l,
          );
          emitChange(next, notes);
        },
      }).render();
      if (editable) {
        const rmHost = el("div");
        row.append(rmHost);
        new Button(rmHost, {
          label: "Remove",
          variant: "ghost",
          size: "sm",
          disabled: p.disabled || lines.length <= 1,
          ariaLabel: `Remove line ${idx + 1}`,
          onClick: () => {
            const next = lines.filter((_, i) => i !== idx);
            emitChange(next.length ? next : [{ invoice_id: "", amount: 0 }], notes);
          },
        }).render();
      }
      linesHost.append(row);
    });
    root.append(linesHost);

    if (editable) {
      const addHost = el("div", { className: "copilot-row", style: "margin-top:0.25rem" });
      root.append(addHost);
      new Button(addHost, {
        label: "Add line",
        variant: "secondary",
        size: "sm",
        disabled: p.disabled,
        onClick: () => {
          emitChange([...lines, { invoice_id: "", amount: 0 }], notes);
        },
      }).render();
      if (p.onSave) {
        new Button(addHost, {
          label: "Save edits",
          variant: "secondary",
          size: "sm",
          disabled: p.disabled,
          onClick: () => p.onSave?.(),
        }).render();
      }
    }

    const notesHost = el("div", { className: "cp-hyp-summary" });
    root.append(notesHost);
    new TextArea(notesHost, {
      id: "hyp-notes",
      label: "Investigation notes / rationale",
      value: notes,
      disabled: p.disabled || !editable,
      rows: 3,
      ariaLabel: "Hypothesis notes",
      onChange: (v) => emitChange(lines, v),
    }).render();

    const summaryText = p.summary?.summary;
    if (summaryText) {
      root.append(
        el(
          "p",
          { className: "copilot-muted", style: "margin-top:0.75rem" },
          summaryText,
        ),
      );
    }

    setChildren(this.root, root);
  }
}
