/**
 * Copilot UI TypeScript-style contracts (JSDoc).
 * These mirror `finance_ops/copilot/types.py` for the workbench layer.
 *
 * @module types
 */

/**
 * @typedef {"accept"|"edit_ready_to_apply"|"reject"|"escalate"|"need_info"} Decision
 */

/**
 * @typedef {"high"|"medium"|"low"|"insufficient"} ConfidenceBand
 */

/**
 * @typedef {Object} Citation
 * @property {string} source_id
 * @property {string} source_type
 * @property {string} [span]
 * @property {string} [claim]
 */

/**
 * @typedef {Object} MatchLine
 * @property {string} invoice_id
 * @property {number} amount
 * @property {string} [rationale]
 */

/**
 * @typedef {Object} MatchHypothesis
 * @property {string} [case_id]
 * @property {string} [payment_id]
 * @property {string|null} [customer_id]
 * @property {MatchLine[]} [lines]
 * @property {Citation[]} [citation_map]
 * @property {ConfidenceBand} [confidence_band]
 * @property {string|null} [model_id]
 * @property {string|null} [prompt_version]
 * @property {boolean} [insufficient_data]
 * @property {string|null} [raw_notes]
 * @property {boolean} [edited]
 */

/**
 * @typedef {Object} InvestigationSummary
 * @property {string} [case_id]
 * @property {string} [summary]
 * @property {ConfidenceBand} [confidence_band]
 * @property {Citation[]} [citation_map]
 */

/**
 * @typedef {Object} EvidenceItem
 * @property {string} source_id
 * @property {string} source_type
 * @property {string} label
 * @property {Record<string, unknown>} [fields]
 * @property {boolean} [stub]
 */

/**
 * @typedef {Object} EvidencePack
 * @property {string} [case_id]
 * @property {EvidenceItem[]} [items]
 * @property {boolean} [email_enabled]
 */

/**
 * @typedef {Object} ApplyGuidancePacket
 * @property {string} case_id
 * @property {string} payment_id
 * @property {string|null} [customer_id]
 * @property {string[]} [invoice_ids]
 * @property {MatchLine[]} [lines]
 * @property {number|null} [total_amount]
 * @property {string} [currency]
 * @property {Citation[]} [citations]
 * @property {string} [actor]
 * @property {string} [decision]
 * @property {string} [timestamp]
 * @property {string|null} [erp_deep_link_hint]
 * @property {string|null} [copy_text]
 * @property {boolean} [warehouse_applied]
 */

/**
 * @typedef {Object} CaseSummary
 * @property {string} case_id
 * @property {string} [status]
 * @property {string|null} [customer_id]
 * @property {string|null} [payment_id]
 * @property {number|null} [amount]
 * @property {string} [currency]
 * @property {number|null} [aging_days]
 * @property {number|null} [match_score]
 * @property {ConfidenceBand|null} [confidence_band]
 * @property {MatchHypothesis|null} [hypothesis]
 */

/**
 * @typedef {Object} CaseDetail
 * @property {string} case_id
 * @property {string} [status]
 * @property {string|null} [customer_id]
 * @property {string|null} [payment_id]
 * @property {number|null} [amount]
 * @property {string} [currency]
 * @property {ConfidenceBand|null} [confidence_band]
 * @property {MatchHypothesis|null} [hypothesis]
 * @property {InvestigationSummary|null} [summary]
 * @property {string|null} [last_decision]
 * @property {string|null} [reason_code]
 * @property {ApplyGuidancePacket|null} [guidance]
 * @property {number|null} [aging_days]
 * @property {number|null} [match_score]
 */

/**
 * @typedef {Object} AuditEvent
 * @property {string} ts
 * @property {string} event
 * @property {string|null} [actor]
 * @property {Record<string, unknown>} [detail]
 */

/**
 * @typedef {Object} ReasonOption
 * @property {string} value
 * @property {string} label
 */

/**
 * @typedef {Object} DigestPayload
 * @property {boolean} [enabled]
 * @property {string} [status]
 * @property {string} [reason]
 * @property {Array<Record<string, unknown>>} [items]
 * @property {Array<Record<string, unknown>>} [excluded]
 * @property {Record<string, unknown>} [gates]
 */

/**
 * Shared UI state props — every interactive component accepts these explicitly.
 *
 * @typedef {Object} UiStateProps
 * @property {boolean} [loading]
 * @property {string|null} [error]
 * @property {boolean} [disabled]
 * @property {string} [ariaLabel]
 * @property {string} [id]
 */

export {};
