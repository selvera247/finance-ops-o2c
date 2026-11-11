/**
 * Copilot workbench composition — wires components to /v1/copilot/* APIs.
 * Hot-path notes: abort in-flight case fetches, reuse investigate payload,
 * avoid queue reload on every case open, split queue vs detail paints,
 * stable handler refs (unlock Component.update shallow-equal), parallel openCase.
 * @module workbench
 */

import { CopilotApi, normalizeApiToken } from "./api.js";
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
import { announce, debounce, isInsufficient } from "./utils.js";

const QUEUE_PAGE = 50;
const EVIDENCE_PAGE = 20;
const AUDIT_PAGE = 20;
const CASE_CACHE_MAX = 24;

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
    /** @type {string|null} */
    this.queueEmptyHint = null;
    /** @type {string|null} */
    this.syncStatusText = null;
    this.queueVisible = QUEUE_PAGE;
    this.evidenceVisible = EVIDENCE_PAGE;
    this.auditVisible = AUDIT_PAGE;
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

    /** @type {AbortController|null} */
    this._caseAbort = null;
    /** @type {AbortController|null} */
    this._queueAbort = null;
    this._syncDebounced = debounce(() => this.refreshQueue(true), 400);

    /** @type {Map<string, {caseData: any, evidence: any[], auditEvents: any[], auditMeta: object, ts: number}>} */
    this._caseCache = new Map();

    // Stable handler refs — Component.update shallow-equal compares functions by identity.
    this._onSelectCase = (id) => this.openCase(id);
    this._onShowMoreQueue = () => {
      this.queueVisible += QUEUE_PAGE;
      this._paintQueue();
    };
    this._onShowMoreEvidence = () => {
      this.evidenceVisible += EVIDENCE_PAGE;
      this._paintDetail();
    };
    this._onShowMoreAudit = () => {
      this.auditVisible += AUDIT_PAGE;
      this._paintDetail();
    };
    this._onInvestigate = () => this.investigate();
    this._onDecision = (d, r) => this.decide(d, r);
    this._onReasonChange = (kind, value) => {
      this.reasons[kind] = value;
    };
    this._onCitationClick = (sid) => {
      const ok = jumpToEvidence(sid, this.root);
      if (!ok) announce(`Evidence source not found: ${sid}`, "assertive");
    };
    this._onHypChange = ({ lines, raw_notes }) => {
      this.draftLines = lines;
      this.draftNotes = raw_notes;
    };
    this._onSaveHypothesis = () => this.saveHypothesis();
    this._onSyncClick = () => this._syncDebounced();

    this._mount();
  }

  _mount() {
    this.root.innerHTML = `
      <a class="copilot-skip-link" href="#copilot-detail">Skip to case detail</a>
      <header class="copilot-shell-header">
        <h1 class="copilot-display-title">Cash-App Exception Copilot</h1>
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

    this._paintSyncBar();

    if (this.showDigest) {
      this.els.digest.hidden = false;
    }

    this._paintAll();
    this.bootstrap();
  }

  _paintSyncBar() {
    if (!this._syncBtn) {
      this.els.sync.innerHTML = "";
      const row = document.createElement("div");
      row.className = "copilot-row";
      row.style.gap = "0.75rem";
      row.style.alignItems = "center";
      row.style.flexWrap = "wrap";
      const btnMount = document.createElement("div");
      row.appendChild(btnMount);
      this._syncMeta = document.createElement("span");
      this._syncMeta.className = "meta";
      this._syncMeta.setAttribute("role", "status");
      row.appendChild(this._syncMeta);
      this.els.sync.appendChild(row);
      this._syncBtn = new Button(btnMount, {
        label: "Sync + refresh",
        ariaLabel: "Sync exception queue from warehouse",
        disabled: false,
        onClick: this._onSyncClick,
      });
      this._syncBtn.render();
    }
    this._syncBtn.update({
      label: this.queueLoading ? "Syncing…" : "Sync + refresh",
      disabled: this.queueLoading,
      onClick: this._onSyncClick,
    });
    this._syncMeta.textContent = this.syncStatusText || "";
    this._syncMeta.hidden = !this.syncStatusText;
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
    // First load syncs once; subsequent Sync clicks are debounced + server-throttled.
    await this.refreshQueue(true);
    if (this.showDigest) {
      await this.refreshDigest();
    }
  }

  _paintQueue() {
    this.queueView.update({
      cases: this.cases,
      loading: this.queueLoading,
      error: this.queueError,
      emptyMessage:
        this.queueEmptyHint ||
        "No cases. Sync the queue to load Spike A / warehouse exceptions.",
      selectedId: this.selectedId,
      visibleCount: this.queueVisible,
      pageSize: QUEUE_PAGE,
      onSelect: this._onSelectCase,
      onShowMore: this._onShowMoreQueue,
    });
  }

  _paintDetail() {
    this.caseHeaderView.update({
      caseData: this.caseData,
      loading: this.detailLoading && !this.caseData,
      error: this.detailError,
    });

    const hyp = this.detailError ? null : this.caseData?.hypothesis || null;
    const insuff = isInsufficient(hyp);
    // Prefer draft string once openCase initialized it (incl. cleared "").
    const workingHyp = hyp
      ? {
          ...hyp,
          lines: this.draftLines || hyp.lines || [],
          raw_notes:
            this.draftNotes != null ? this.draftNotes : hyp.raw_notes || "",
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
      onInvestigate: this._onInvestigate,
      onDecision: this._onDecision,
      onReasonChange: this._onReasonChange,
    });

    this.hypothesisView.update({
      hypothesis: workingHyp,
      summary: this.caseData?.summary || null,
      loading: this.detailLoading && !workingHyp,
      disabled: this.actionBusy || !this.caseData || this.detailLoading,
      editable: Boolean(this.caseData) && !this.detailLoading && !this.detailError,
      onCitationClick: this._onCitationClick,
      onChange: this._onHypChange,
      onSave: this._onSaveHypothesis,
    });

    this.guidanceView.update({
      guidance: this.detailError ? null : this.caseData?.guidance || null,
      loading: false,
    });

    this.evidenceView.update({
      items: this.detailError ? [] : this.evidence,
      loading: this.detailLoading && !this.evidence.length,
      thinEvidence: insuff,
      visibleCount: this.evidenceVisible,
      onShowMore: this._onShowMoreEvidence,
    });

    this.auditView.update({
      events: this.detailError ? [] : this.auditEvents,
      decisionActor: this.detailError ? undefined : this.auditMeta.decision_actor,
      decisionAt: this.detailError ? undefined : this.auditMeta.decision_at,
      confidenceBand: this.detailError ? undefined : this.auditMeta.confidence_band,
      loading: this.detailLoading && !this.auditEvents.length,
      visibleCount: this.auditVisible,
      onShowMore: this._onShowMoreAudit,
    });
  }

  _paintDigest() {
    if (this.showDigest) {
      this.digestView.update({ digest: this.digest });
    }
  }

  _paintAll() {
    this._paintQueue();
    this._paintDetail();
    this._paintDigest();
  }

  /**
   * @param {string} caseId
   * @param {{caseData?: any, evidence?: any[], auditEvents?: any[], auditMeta?: object}} snap
   */
  _rememberCase(caseId, snap) {
    this._caseCache.delete(caseId);
    this._caseCache.set(caseId, { ...snap, ts: Date.now() });
    while (this._caseCache.size > CASE_CACHE_MAX) {
      const oldest = this._caseCache.keys().next().value;
      this._caseCache.delete(oldest);
    }
  }

  /**
   * @param {boolean} [sync]
   */
  async refreshQueue(sync = false) {
    this._queueAbort?.abort();
    this._queueAbort = new AbortController();
    const { signal } = this._queueAbort;

    this.queueLoading = true;
    this.queueError = null;
    this.queueEmptyHint = null;
    this._paintSyncBar();
    this._paintQueue();
    try {
      const q = await this.api.queue(
        { sync, lane: "cash_app", detail: "summary" },
        { signal },
      );
      if (signal.aborted) return;
      this.cases = q.cases || [];
      this.queueVisible = Math.min(QUEUE_PAGE, this.cases.length || QUEUE_PAGE);
      this.queueLoading = false;

      const syncMeta = q.sync || null;
      if (sync && syncMeta) {
        const pack = syncMeta.seed?.pack;
        const seeded =
          syncMeta.seed?.seeded || syncMeta.seed?.status === "success"
            ? ` · seeded ${pack || "demo"}`
            : "";
        if (syncMeta.status === "throttled") {
          this.syncStatusText = `Sync throttled — retry in ${syncMeta.retry_after_sec || "?"}s`;
        } else if (syncMeta.hint && !this.cases.length) {
          // Operator hint is not a request failure — keep empty-state, not error UI.
          this.syncStatusText = syncMeta.hint;
          this.queueEmptyHint = syncMeta.hint;
        } else {
          this.syncStatusText = `Synced ${syncMeta.synced_count ?? 0} · payments ${syncMeta.payment_count ?? 0}${seeded}`;
        }
      } else if (!sync) {
        this.syncStatusText = this.syncStatusText || null;
      }

      if (!this.cases.length && syncMeta?.payment_count === 0 && !this.queueError) {
        this.queueEmptyHint =
          syncMeta.hint ||
          "Sync returned no unmatched payments — warehouse may be empty.";
      }

      announce(`Queue loaded, ${this.cases.length} cases`);
      this._paintSyncBar();
      this._paintQueue();
    } catch (err) {
      if (err?.name === "AbortError" || signal.aborted) return;
      this.queueLoading = false;
      this.queueError = String(err.message || err);
      this.syncStatusText = this.queueError;
      announce(this.queueError, "assertive");
      this._paintSyncBar();
      this._paintQueue();
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
    this._paintDigest();
  }

  /**
   * Patch selected queue row status without a full GET /queue.
   * @param {string} caseId
   * @param {Partial<import('./types.js').CaseSummary>} patch
   */
  _patchCaseRow(caseId, patch) {
    this.cases = this.cases.map((c) =>
      c.case_id === caseId ? { ...c, ...patch } : c,
    );
    this._paintQueue();
  }

  /** @param {string} caseId */
  async openCase(caseId) {
    this._caseAbort?.abort();
    this._caseAbort = new AbortController();
    const { signal } = this._caseAbort;

    this.selectedId = caseId;
    this.detailLoading = true;
    this.detailError = null;
    this.actionError = null;
    this.draftLines = null;
    this.draftNotes = "";
    this.evidenceVisible = EVIDENCE_PAGE;
    this.auditVisible = AUDIT_PAGE;

    // Optimistic header from queue summary — paint before any network.
    const queueRow = this.cases.find((c) => c.case_id === caseId) || null;
    const cached = this._caseCache.get(caseId) || null;
    if (cached) {
      this.caseData = cached.caseData;
      this.evidence = cached.evidence || [];
      this.auditEvents = cached.auditEvents || [];
      this.auditMeta = cached.auditMeta || {};
      this.draftLines = this.caseData?.hypothesis?.lines
        ? this.caseData.hypothesis.lines.map((l) => ({ ...l }))
        : null;
      this.draftNotes = this.caseData?.hypothesis?.raw_notes || "";
    } else if (queueRow) {
      this.caseData = { ...queueRow };
      this.evidence = [];
      this.auditEvents = [];
      this.auditMeta = {};
    } else {
      this.caseData = null;
      this.evidence = [];
      this.auditEvents = [];
      this.auditMeta = {};
    }

    // Selection highlight only — do not refetch the whole queue.
    this._paintQueue();
    this._paintDetail();
    this.els.detailStatus.textContent = `Opening ${caseId}`;

    try {
      // Fire case + evidence + audit together (one wave) — cut sequential RTT.
      const settled = await Promise.allSettled([
        this.api.case(caseId, { signal }),
        this.api.evidence(caseId, this.actor, { signal }),
        this.api.audit(caseId, { signal }),
      ]);
      if (signal.aborted || this.selectedId !== caseId) return;

      const cRes = settled[0];
      const ev = settled[1];
      const au = settled[2];

      if (cRes.status === "rejected") {
        if (cRes.reason?.name === "AbortError") return;
        throw cRes.reason;
      }
      const c = cRes.value;
      this.caseData = c.case || this.caseData;
      this.draftLines = this.caseData?.hypothesis?.lines
        ? this.caseData.hypothesis.lines.map((l) => ({ ...l }))
        : null;
      this.draftNotes = this.caseData?.hypothesis?.raw_notes || "";

      if (ev.status === "fulfilled") {
        this.evidence = ev.value.evidence?.items || [];
      } else if (ev.reason?.name !== "AbortError") {
        this.evidence = [];
      }
      if (au.status === "fulfilled") {
        this.auditEvents = au.value.audit || [];
        this.auditMeta = {
          decision_actor: au.value.decision_actor,
          decision_at: au.value.decision_at,
          confidence_band: au.value.confidence_band,
        };
      } else if (au.reason?.name !== "AbortError") {
        this.auditEvents = [];
        this.auditMeta = {};
      }
      const sideErr =
        (ev.status === "rejected" && ev.reason?.name !== "AbortError" && ev.reason) ||
        (au.status === "rejected" && au.reason?.name !== "AbortError" && au.reason) ||
        null;
      if (sideErr) {
        this.actionError = String(sideErr.message || sideErr).trim() || "Request failed";
        announce(this.actionError, "assertive");
      }
      this.detailLoading = false;
      this._rememberCase(caseId, {
        caseData: this.caseData,
        evidence: this.evidence,
        auditEvents: this.auditEvents,
        auditMeta: this.auditMeta,
      });
      announce(`Opened case ${caseId}`);
      this._paintDetail();
    } catch (err) {
      if (err?.name === "AbortError" || signal.aborted) return;
      this.detailLoading = false;
      this.caseData = null;
      this.evidence = [];
      this.auditEvents = [];
      this.auditMeta = {};
      this.draftLines = null;
      this.draftNotes = "";
      const raw = String(err.message || err).trim();
      this.detailError = raw || `Failed to open case (HTTP ${err.status || "?"})`;
      const payload = err.payload?.detail || err.payload;
      if (
        this.detailError.includes("cross_customer") ||
        payload?.error === "cross_customer_denied"
      ) {
        this.detailError = `Cross-customer retrieve denied. ${this.detailError}`;
      }
      announce(this.detailError, "assertive");
      this._paintDetail();
    }
  }

  async investigate() {
    if (!this.selectedId) return;
    const caseId = this.selectedId;
    this.investigating = true;
    this.actionError = null;
    this._paintDetail();
    try {
      const out = await this.api.investigate(caseId, { actor: this.actor });
      if (this.selectedId !== caseId) return;
      // Reuse investigate response — skip openCase (would rebuild evidence again).
      if (out.hypothesis || out.summary) {
        this.caseData = {
          ...(this.caseData || { case_id: caseId }),
          hypothesis: out.hypothesis || this.caseData?.hypothesis,
          summary: out.summary || this.caseData?.summary,
          confidence_band: out.hypothesis?.confidence_band,
        };
        this.draftLines = out.hypothesis?.lines
          ? out.hypothesis.lines.map((l) => ({ ...l }))
          : this.draftLines;
        this.draftNotes = out.hypothesis?.raw_notes || this.draftNotes;
      }
      if (out.evidence?.items) {
        this.evidence = out.evidence.items;
        this.evidenceVisible = EVIDENCE_PAGE;
      }
      this._patchCaseRow(caseId, {
        confidence_band: out.hypothesis?.confidence_band,
        insufficient_data: out.hypothesis?.insufficient_data,
      });
      // Refresh audit only (cheap overlay read) — evidence already in hand.
      try {
        const a = await this.api.audit(caseId);
        if (this.selectedId === caseId) {
          this.auditEvents = a.audit || [];
          this.auditVisible = AUDIT_PAGE;
          this.auditMeta = {
            decision_actor: a.decision_actor,
            decision_at: a.decision_at,
            confidence_band: a.confidence_band,
          };
        }
      } catch {
        /* non-fatal */
      }
      this._rememberCase(caseId, {
        caseData: this.caseData,
        evidence: this.evidence,
        auditEvents: this.auditEvents,
        auditMeta: this.auditMeta,
      });
      announce("Investigation complete");
    } catch (err) {
      this.actionError = String(err.message || err);
      announce(this.actionError, "assertive");
    } finally {
      this.investigating = false;
      if (this.selectedId === caseId) {
        this._paintDetail();
      }
    }
  }

  async saveHypothesis() {
    if (!this.selectedId || !this.draftLines) return;
    const caseId = this.selectedId;
    this.actionBusy = true;
    this.actionError = null;
    this._paintDetail();
    try {
      const out = await this.api.updateHypothesis(caseId, {
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
      if (this.selectedId !== caseId) return;
      if (out.hypothesis && this.caseData) {
        this.caseData = { ...this.caseData, hypothesis: out.hypothesis };
      }
      announce("Hypothesis saved");
    } catch (err) {
      if (this.selectedId !== caseId) return;
      this.actionError = String(err.message || err);
      announce(this.actionError, "assertive");
    } finally {
      if (this.selectedId === caseId) {
        this.actionBusy = false;
        this._paintDetail();
      } else {
        this.actionBusy = false;
      }
    }
  }

  /**
   * @param {string} decision
   * @param {string|null} reasonCode
   */
  async decide(decision, reasonCode) {
    if (!this.selectedId) return;
    const caseId = this.selectedId;
    this.actionBusy = true;
    this.actionError = null;
    this._paintDetail();
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
      const out = await this.api.decide(caseId, body);
      if (this.selectedId !== caseId) return;
      if (out.guidance && this.caseData) {
        this.caseData = {
          ...this.caseData,
          guidance: out.guidance,
          status: out.case_status || this.caseData.status,
          last_decision: out.decision,
          reason_code: out.reason_code || reasonCode,
        };
      } else if (this.caseData) {
        this.caseData = {
          ...this.caseData,
          status: out.case_status || this.caseData.status,
          last_decision: out.decision,
          reason_code: out.reason_code || reasonCode,
        };
      }
      this._patchCaseRow(caseId, {
        status: out.case_status,
        last_decision: out.decision,
        reason_code: out.reason_code || reasonCode,
      });
      if (out.guidance) {
        announce("Guidance packet ready");
      } else {
        announce(`Decision recorded: ${decision}`);
      }
      // Patch-only when status stays in open set; full refresh when terminal / reorder risk.
      const terminal = ["resolved", "rejected", "closed"].includes(
        String(out.case_status || ""),
      );
      if (terminal) {
        await this.refreshQueue(false);
        if (this.selectedId !== caseId) return;
      }
      try {
        const a = await this.api.audit(caseId);
        if (this.selectedId === caseId) {
          this.auditEvents = a.audit || [];
          this.auditMeta = {
            decision_actor: a.decision_actor,
            decision_at: a.decision_at,
            confidence_band: a.confidence_band,
          };
        }
      } catch {
        /* non-fatal */
      }
      this._rememberCase(caseId, {
        caseData: this.caseData,
        evidence: this.evidence,
        auditEvents: this.auditEvents,
        auditMeta: this.auditMeta,
      });
    } catch (err) {
      if (this.selectedId !== caseId) return;
      this.actionError = String(err.message || err);
      announce(this.actionError, "assertive");
    } finally {
      this.actionBusy = false;
      if (this.selectedId === caseId) {
        this._paintDetail();
      }
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
      token: normalizeApiToken(
        params.get("token") ||
          window.localStorage.getItem("FINANCE_OPS_API_TOKEN"),
      ),
    }),
  });
}

main();
