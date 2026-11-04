/**
 * Thin Copilot HTTP client — no implicit globals; pass baseUrl / token explicitly.
 * @module api
 */

/**
 * @typedef {Object} CopilotApiOptions
 * @property {string} [baseUrl] - Origin prefix (default "")
 * @property {string|null} [token] - Write token for mutating routes
 * @property {typeof fetch} [fetchImpl]
 */

export class CopilotApi {
  /** @param {CopilotApiOptions} [opts] */
  constructor(opts = {}) {
    this.baseUrl = (opts.baseUrl || "").replace(/\/$/, "");
    this.token = opts.token ?? null;
    this.fetchImpl = opts.fetchImpl || fetch.bind(globalThis);
  }

  /**
   * @param {string} path
   * @param {RequestInit & { json?: unknown }} [opts]
   */
  async request(path, opts = {}) {
    const headers = new Headers(opts.headers || {});
    if (opts.json !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
      headers.set("X-API-Token", this.token);
    }
    const { json, ...rest } = opts;
    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...rest,
      headers,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail?.error || data.detail || data.error || res.statusText;
      const err = new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  status() {
    return this.request("/v1/copilot/status");
  }

  /**
   * @param {{ sync?: boolean, lane?: string, status?: string, limit?: number }} [q]
   */
  queue(q = {}) {
    const params = new URLSearchParams();
    if (q.sync) params.set("sync", "true");
    if (q.lane) params.set("lane", q.lane);
    if (q.status) params.set("status", q.status);
    if (q.limit != null) params.set("limit", String(q.limit));
    const qs = params.toString();
    return this.request(`/v1/copilot/queue${qs ? `?${qs}` : ""}`);
  }

  /**
   * @param {{ force?: boolean, sync?: boolean, limit?: number }} [q]
   */
  digest(q = {}) {
    const params = new URLSearchParams();
    if (q.force) params.set("force", "true");
    if (q.sync) params.set("sync", "true");
    if (q.limit != null) params.set("limit", String(q.limit));
    const qs = params.toString();
    return this.request(`/v1/copilot/digest${qs ? `?${qs}` : ""}`);
  }

  /** @param {string} caseId */
  case(caseId) {
    return this.request(`/v1/copilot/cases/${encodeURIComponent(caseId)}`);
  }

  /**
   * @param {string} caseId
   * @param {string} [actor]
   */
  evidence(caseId, actor = "workbench") {
    const q = new URLSearchParams({ actor });
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/evidence?${q}`,
    );
  }

  /** @param {string} caseId */
  audit(caseId) {
    return this.request(`/v1/copilot/cases/${encodeURIComponent(caseId)}/audit`);
  }

  /**
   * @param {string} caseId
   * @param {{ actor?: string }} [body]
   */
  investigate(caseId, body = {}) {
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/investigate`,
      { method: "POST", json: { actor: body.actor || "workbench" } },
    );
  }

  /**
   * @param {string} caseId
   * @param {{ lines: import('./types.js').MatchLine[], raw_notes?: string|null, confidence_band?: string|null, actor?: string }} body
   */
  updateHypothesis(caseId, body) {
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/hypothesis`,
      {
        method: "POST",
        json: {
          lines: body.lines,
          raw_notes: body.raw_notes ?? null,
          confidence_band: body.confidence_band ?? null,
          actor: body.actor || "workbench",
        },
      },
    );
  }

  /**
   * @param {string} caseId
   * @param {{ decision: string, actor?: string, reason_code?: string|null, notes?: string|null, hypothesis?: unknown }} body
   */
  decide(caseId, body) {
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/decision`,
      {
        method: "POST",
        json: {
          decision: body.decision,
          actor: body.actor || "workbench",
          reason_code: body.reason_code ?? null,
          notes: body.notes ?? null,
          hypothesis: body.hypothesis ?? null,
        },
      },
    );
  }
}
