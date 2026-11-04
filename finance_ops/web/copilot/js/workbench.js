/**
 * Copilot workbench composition — wires components to /v1/copilot/* APIs.
 * @module workbench
 */

import { CopilotApi } from "./api.js";
import {
  ActionBar,
  AuditTimeline,
  Banner,
  Button,
  CaseHeader,
  DigestPreview,
  EvidencePane,
  ExceptionQueue,
  GuidancePacketView,
  HypothesisDraft,
  jumpToEvidence,
} from "./components/index.js";
import { announce, isInsufficient } from "./utils.js";

/**
 * @typedef {Object} WorkbenchOptions
 * @property {HTMLElement} root
 * @property {CopilotApi} [api]
 * @property {string} [actor]
 * @property {boolean} [showDigest]
 */

export class CopilotWorkbench {
  /** @param {WorkbenchOptions} opts */
  constructor(opts) {
    this.root = opts.root;
    this.api = opts.api || new CopilotApi();
    this.actor = opts.actor || "workbench";
    this.showDigest = Boolean(opts.showDigest);

    /** @type {string|null} */
    this.selectedId = null;
    /** @type {import('./types.js').CaseSummary[]} */
    this.cases = [];
    /** @type {import('./types.js').CaseDetail|null} */
    this.caseData = null;
    /** @type {import('./types.js').EvidenceItem[]} */
    this.evidence = [];
    /** @type {import('./types.js').AuditEvent[]} */
    this.auditEvents = [];
    this.auditMeta = {};
    /** @type {import('./types.js').DigestPayload|null} */
    this.digest = null;

    this.queueLoading = true;
    this.queueError = null;
    this.detailLoading = false;
    this.detailError = null;
    this.investigating = false;
    this.actionError = null;
    this.actionBusy = false;
    this.statusText = "loading…";

    this.draftLines = null;
    this.draftNotes = "";
    this.reasons = {
      reject: "reject_wrong_customer",
      escalate: "escalate_materiality",
      need_info: "need_info_remittance",
    };

    this._mount();
  }

  _mount() {
    this.root.innerHTML = `
      <a class="copilot-skip-link" href="#copilot-detail">Skip to case detail</a>
      <header class="copilot-shell-header">
        <h1>Cash-App Exception Copilot</h1>
        <span class="meta" id="wb-mode-meta"></span>
        <nav aria-label="Copilot pages">
          <a href="/copilot" aria-current="page">Workbench</a>
          <a href="/copilot/examples">Examples</a>
          <a href="/docs">API</a>
        </nav>
      </header>
      <div id="wb-guidance-banner"></div>
      <main class="copilot-layout">
        <aside class="copilot-queue-col" aria-label="Queue column">
          <div id="wb-sync" class="copilot-row" style="margin-bottom:0.75rem"></div>
          <div id="wb-queue"></div>
          <div id="wb-digest" style="margin-top:1rem" hidden></div>
        </aside>
        <section class="copilot-detail-col" id="copilot-detail" tabindex="-1" aria-label="Case detail">
          <div id="wb-detail-status" class="copilot-live" aria-live="polite" aria-atomic="true"></div>
          <div class="copilot-panel" id="wb-case-panel">
            <div id="wb-case-header"></div>
            <div id="wb-actions" style="margin-top:0.75rem"></div>
          </div>
          <div class="copilot-panel">
            <h2>Hypothesis</h2>
            <div id="wb-hypothesis"></div>
          </div>
          <div class="copilot-panel">
            <h2>ApplyGuidancePacket</h2>
            <div id="wb-guidance"></div>
          </div>
          <div class="copilot-panel">
            <h2>Evidence</h2>
            <div id="wb-evidence"></div>
          </div>
          <div class="copilot-panel">
            <h2>Audit</h2>
            <div id="wb-audit"></div>
          </div>
        </section>
      </main>
      <div id="wb-modal-root"></div>
    `;

    this.els = {
      modeMeta: this.root.querySelector("#wb-mode-meta"),
      guidanceBanner: this.root.querySelector("#wb-guidance-banner"),
      sync: this.root.querySelector("#wb-sync"),
      queue: this.root.querySelector("#wb-queue"),
      digest: this.root.querySelector("#wb-digest"),
      detailStatus: this.root.querySelector("#wb-detail-status"),
      caseHeader: this.root.querySelector("#wb-case-header"),
      actions: this.root.querySelector("#wb-actions"),
      hypothesis: this.root.querySelector("#wb-hypothesis"),
      guidance: this.root.querySelector("#wb-guidance"),
      evidence: this.root.querySelector("#wb-evidence"),
      audit: this.root.querySelector("#wb-audit"),
    };

    this.queueView = new ExceptionQueue(this.els.queue, {});
    this.caseHeaderView = new CaseHeader(this.els.caseHeader, {});
    this.actionBar = new ActionBar(this.els.actions, {});
    this.hypothesisView = new HypothesisDraft(this.els.hypothesis, {});
    this.guidanceView = new GuidancePacketView(this.els.guidance, {});
    this.evidenceView = new EvidencePane(this.els.evidence, {});
    this.auditView = new AuditTimeline(this.els.audit, {});
    this.digestView = new DigestPreview(this.els.digest, {});

    new Banner(this.els.guidanceBanner, {
      variant: "info",
      title: "Guidance-only apply",
      message:
        "Accept emits an ApplyGuidancePacket for ERP copy/deep-link. Warehouse apply requires FINANCE_OPS_DEMO_APPLY=1.",
    }).render();

    new Button(this.els.sync, {
      label: "Sync + refresh",
      ariaLabel: "Sync exception queue from warehouse",
      onClick: () => this.refreshQueue(true),
    }).render();

    if (this.showDigest) {
      this.els.digest.hidden = false;
    }

    this._paint();
    this.bootstrap();
  }

  async bootstrap() {
    try {
      const s = await this.api.status();
      this.statusText = `mode ${s.prototype_mode}/${s.mode} · email=${s.email_evidence} · demo_apply=${s.demo_apply} · digest=${s.digest_enabled}`;
      this.els.modeMeta.textContent = this.statusText;
      if (s.digest_enabled) {
        this.showDigest = true;
        this.els.digest.hidden = false;
      }
    } catch (err) {
      this.statusText = String(err.message || err);
      this.els.modeMeta.textContent = this.statusText;
    }
    await this.refreshQueue(true);
    if (this.showDigest) {
      await this.refreshDigest();
    }
  }

  _paint() {
    this.queueView.update({
      cases: this.cases,
      loading: this.queueLoading,
      error: this.queueError,
      selectedId: this.selectedId,
      onSelect: (id) => this.openCase(id),
    });

    this.caseHeaderView.update({
      caseData: this.caseData,
      loading: this.detailLoading && !this.caseData,
      error: this.detailError,
    });

    const hyp = this.caseData?.hypothesis || null;
    const insuff = isInsufficient(hyp);
    const workingHyp = hyp
      ? {
          ...hyp,
          lines: this.draftLines || hyp.lines || [],
          raw_notes: this.draftNotes || hyp.raw_notes || "",
        }
      : null;

    this.actionBar.update({
      loading: this.actionBusy,
      error: this.actionError,
      disabled: !this.caseData || this.detailLoading,
      acceptDisabled: !this.caseData || insuff,
      investigating: this.investigating,
      rejectReason: this.reasons.reject,
      escalateReason: this.reasons.escalate,
      needInfoReason: this.reasons.need_info,
      onInvestigate: () => this.investigate(),
      onDecision: (d, r) => this.decide(d, r),
      onReasonChange: (kind, value) => {
        this.reasons[kind] = value;
      },
    });

    this.hypothesisView.update({
      hypothesis: workingHyp,
      summary: this.caseData?.summary || null,
      loading: this.detailLoading && !workingHyp,
      disabled: this.actionBusy || !this.caseData,
      editable: Boolean(this.caseData),
      onCitationClick: (sid) => {
        const ok = jumpToEvidence(sid, this.root);
        if (!ok) announce(`Evidence source not found: ${sid}`, "assertive");
      },
      onChange: ({ lines, raw_notes }) => {
        this.draftLines = lines;
        this.draftNotes = raw_notes;
      },
      onSave: () => this.saveHypothesis(),
    });

    this.guidanceView.update({
      guidance: this.caseData?.guidance || null,
      loading: false,
    });

    this.evidenceView.update({
      items: this.evidence,
      loading: this.detailLoading && !this.evidence.length,
      thinEvidence: insuff,
    });

    this.auditView.update({
      events: this.auditEvents,
      decisionActor: this.auditMeta.decision_actor,
      decisionAt: this.auditMeta.decision_at,
      confidenceBand: this.auditMeta.confidence_band,
      loading: this.detailLoading && !this.auditEvents.length,
    });

    if (this.showDigest) {
      this.digestView.update({ digest: this.digest });
    }
  }

  /**
   * @param {boolean} [sync]
   */
  async refreshQueue(sync = false) {
    this.queueLoading = true;
    this.queueError = null;
    this._paint();
    try {
      const q = await this.api.queue({ sync, lane: "cash_app" });
      this.cases = q.cases || [];
      this.queueLoading = false;
      announce(`Queue loaded, ${this.cases.length} cases`);
      this._paint();
    } catch (err) {
      this.queueLoading = false;
      this.queueError = String(err.message || err);
      announce(this.queueError, "assertive");
      this._paint();
    }
  }

  async refreshDigest() {
    try {
      this.digest = await this.api.digest({ force: true });
    } catch (err) {
      this.digest = {
        enabled: false,
        status: "error",
        reason: String(err.message || err),
        items: [],
      };
    }
    this._paint();
  }

  /** @param {string} caseId */
  async openCase(caseId) {
    this.selectedId = caseId;
    this.detailLoading = true;
    this.detailError = null;
    this.actionError = null;
    this.draftLines = null;
    this.draftNotes = "";
    this._paint();
    this.els.detailStatus.textContent = `Opening ${caseId}`;

    try {
      const [c, e, a] = await Promise.all([
        this.api.case(caseId),
        this.api.evidence(caseId, this.actor),
        this.api.audit(caseId),
      ]);
      this.caseData = c.case || null;
      this.evidence = e.evidence?.items || [];
      this.auditEvents = a.audit || [];
      this.auditMeta = {
        decision_actor: a.decision_actor,
        decision_at: a.decision_at,
        confidence_band: a.confidence_band,
      };
      this.draftLines = this.caseData?.hypothesis?.lines
        ? this.caseData.hypothesis.lines.map((l) => ({ ...l }))
        : null;
      this.draftNotes = this.caseData?.hypothesis?.raw_notes || "";
      this.detailLoading = false;
      announce(`Opened case ${caseId}`);
      this._paint();
      await this.refreshQueue(false);
    } catch (err) {
      this.detailLoading = false;
      this.detailError = String(err.message || err);
      const payload = err.payload?.detail || err.payload;
      if (
        typeof this.detailError === "string" &&
        (this.detailError.includes("cross_customer") ||
          payload?.error === "cross_customer_denied")
      ) {
        this.detailError = `Cross-customer retrieve denied. ${this.detailError}`;
      }
      announce(this.detailError, "assertive");
      this._paint();
    }
  }

  async investigate() {
    if (!this.selectedId) return;
    this.investigating = true;
    this.actionError = null;
    this._paint();
    try {
      await this.api.investigate(this.selectedId, { actor: this.actor });
      announce("Investigation complete");
      await this.openCase(this.selectedId);
    } catch (err) {
      this.actionError = String(err.message || err);
      announce(this.actionError, "assertive");
    } finally {
      this.investigating = false;
      this._paint();
    }
  }

  async saveHypothesis() {
    if (!this.selectedId || !this.draftLines) return;
    this.actionBusy = true;
    this.actionError = null;
    this._paint();
    try {
      await this.api.updateHypothesis(this.selectedId, {
        lines: this.draftLines
          .filter((l) => l.invoice_id)
          .map((l) => ({
            invoice_id: l.invoice_id,
            amount: Number(l.amount) || 0,
            rationale: l.rationale || null,
          })),
        raw_notes: this.draftNotes,
        actor: this.actor,
      });
      announce("Hypothesis saved");
      await this.openCase(this.selectedId);
    } catch (err) {
      this.actionError = String(err.message || err);
      announce(this.actionError, "assertive");
    } finally {
      this.actionBusy = false;
      this._paint();
    }
  }

  /**
   * @param {string} decision
   * @param {string|null} reasonCode
   */
  async decide(decision, reasonCode) {
    if (!this.selectedId) return;
    this.actionBusy = true;
    this.actionError = null;
    this._paint();
    try {
      const body = {
        decision,
        actor: this.actor,
        reason_code: reasonCode,
      };
      if (decision === "edit_ready_to_apply" && this.draftLines) {
        body.hypothesis = {
          lines: this.draftLines
            .filter((l) => l.invoice_id)
            .map((l) => ({
              invoice_id: l.invoice_id,
              amount: Number(l.amount) || 0,
              rationale: l.rationale || null,
            })),
          raw_notes: this.draftNotes,
        };
      }
      const out = await this.api.decide(this.selectedId, body);
      if (out.guidance) {
        announce("Guidance packet ready");
      } else {
        announce(`Decision recorded: ${decision}`);
      }
      await this.openCase(this.selectedId);
      await this.refreshQueue(false);
    } catch (err) {
      this.actionError = String(err.message || err);
      announce(this.actionError, "assertive");
    } finally {
      this.actionBusy = false;
      this._paint();
    }
  }
}

function main() {
  const root = document.getElementById("app");
  if (!root) return;
  const params = new URLSearchParams(window.location.search);
  // eslint-disable-next-line no-new
  new CopilotWorkbench({
    root,
    actor: params.get("actor") || "workbench",
    showDigest: params.get("digest") === "1",
    api: new CopilotApi({
      token: params.get("token") || window.localStorage.getItem("FINANCE_OPS_API_TOKEN"),
    }),
  });
}

main();
