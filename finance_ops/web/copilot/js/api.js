/**
 * Thin Copilot HTTP client — no implicit globals; pass baseUrl / token explicitly.
 * Supports AbortSignal for in-flight cancel on rapid case switches.
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
    if (rest.signal?.aborted) {
      const err = new Error("aborted");
      err.name = "AbortError";
      throw err;
    }
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

  status(opts = {}) {
    return this.request("/v1/copilot/status", opts);
  }

  /**
   * @param {{ sync?: boolean, lane?: string, status?: string, limit?: number, detail?: string }} [q]
   * @param {RequestInit} [opts]
   */
  queue(q = {}, opts = {}) {
    const params = new URLSearchParams();
    if (q.sync) params.set("sync", "true");
    if (q.lane) params.set("lane", q.lane);
    if (q.status) params.set("status", q.status);
    if (q.limit != null) params.set("limit", String(q.limit));
    // List views default to slim payloads (hypothesis/guidance omitted).
    params.set("detail", q.detail || "summary");
    const qs = params.toString();
    return this.request(`/v1/copilot/queue${qs ? `?${qs}` : ""}`, opts);
  }

  /**
   * @param {{ force?: boolean, sync?: boolean, limit?: number }} [q]
   * @param {RequestInit} [opts]
   */
  digest(q = {}, opts = {}) {
    const params = new URLSearchParams();
    if (q.force) params.set("force", "true");
    if (q.sync) params.set("sync", "true");
    if (q.limit != null) params.set("limit", String(q.limit));
    const qs = params.toString();
    return this.request(`/v1/copilot/digest${qs ? `?${qs}` : ""}`, opts);
  }

  /** @param {string} caseId @param {RequestInit} [opts] */
  case(caseId, opts = {}) {
    return this.request(`/v1/copilot/cases/${encodeURIComponent(caseId)}`, opts);
  }

  /**
   * @param {string} caseId
   * @param {string} [actor]
   * @param {RequestInit} [opts]
   */
  evidence(caseId, actor = "workbench", opts = {}) {
    const q = new URLSearchParams({ actor });
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/evidence?${q}`,
      opts,
    );
  }

  /** @param {string} caseId @param {RequestInit} [opts] */
  audit(caseId, opts = {}) {
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/audit`,
      opts,
    );
  }

  /**
   * @param {string} caseId
   * @param {{ actor?: string }} [body]
   * @param {RequestInit} [opts]
   */
  investigate(caseId, body = {}, opts = {}) {
    return this.request(
      `/v1/copilot/cases/${encodeURIComponent(caseId)}/investigate`,
      { method: "POST", json: { actor: body.actor || "workbench" }, ...opts },
    );
  }

  /**
   * @param {string} caseId
   * @param {{ lines: import('./types.js').MatchLine[], raw_notes?: string|null, confidence_band?: string|null, actor?: string }} body
   * @param {RequestInit} [opts]
   */
  updateHypothesis(caseId, body, opts = {}) {
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
        ...opts,
      },
    );
  }

  /**
   * @param {string} caseId
   * @param {{ decision: string, actor?: string, reason_code?: string|null, notes?: string|null, hypothesis?: unknown }} body
   * @param {RequestInit} [opts]
   */
  decide(caseId, body, opts = {}) {
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
        ...opts,
      },
    );
  }
}
