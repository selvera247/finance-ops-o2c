"""File-backed Copilot case overlays (hypothesis, audit, guidance).

Exception projection stays in ar_exceptions; this store holds Copilot-specific
state so we do not break existing queue schema.

Discovery-minimum audit fields live on investigate/decision events and on the
overlay document (raw + edited hypothesis, citations, actor, timestamps).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from finance_ops.copilot.types import (
    ApplyGuidancePacket,
    AuditEvent,
    InvestigationSummary,
    MatchHypothesis,
)
from finance_ops.lib.paths import REPO_ROOT

# Cap retained audit events per case (oldest dropped). Override via env.
_MAX_AUDIT = max(20, int(os.getenv("COPILOT_MAX_AUDIT_EVENTS", "100") or "100"))

# Uvicorn runs sync routes in a threadpool; GET /evidence appends audit while
# investigate/decide persist hypothesis — unlocked RMW lost updates.
_OVERLAY_GUARDS: dict[str, threading.Lock] = {}
_OVERLAY_GUARDS_LOCK = threading.Lock()


def _overlay_lock(case_id: str) -> threading.Lock:
    with _OVERLAY_GUARDS_LOCK:
        lock = _OVERLAY_GUARDS.get(case_id)
        if lock is None:
            lock = threading.Lock()
            _OVERLAY_GUARDS[case_id] = lock
        return lock


def _root() -> Path:
    base = REPO_ROOT / ".copilot" / "cases"
    base.mkdir(parents=True, exist_ok=True)
    return base


def case_path(case_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in case_id)
    return _root() / f"{safe}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_overlay(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "hypothesis": None,
        "raw_hypothesis": None,
        "summary": None,
        "guidance": None,
        "audit": [],
        "last_decision": None,
        "reason_code": None,
        "decision_actor": None,
        "decision_at": None,
        "confidence_band": None,
        "citation_map": None,
    }


def load_overlay(case_id: str) -> dict[str, Any]:
    path = case_path(case_id)
    if not path.is_file():
        return _empty_overlay(case_id)
    return json.loads(path.read_text(encoding="utf-8"))


def load_overlays(case_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch-load overlays for a queue page (one open per id; shared empty template)."""
    out: dict[str, dict[str, Any]] = {}
    for case_id in case_ids:
        out[case_id] = load_overlay(case_id)
    return out


def save_overlay(case_id: str, data: dict[str, Any]) -> dict[str, Any]:
    path = case_path(case_id)
    data = {**data, "case_id": case_id, "updated_at": _now()}
    # Compact JSON — indent=2 doubled overlay size on every investigate write.
    # Atomic replace avoids torn reads if another thread loads mid-write.
    payload = json.dumps(data, separators=(",", ":"), default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return data


def update_overlay(
    case_id: str,
    mutator: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """Single load → mutate → save cycle for multi-field updates (per-case lock)."""
    with _overlay_lock(case_id):
        overlay = load_overlay(case_id)
        mutator(overlay)
        return save_overlay(case_id, overlay)


def _trim_audit(audit: list[Any]) -> list[Any]:
    if len(audit) <= _MAX_AUDIT:
        return audit
    return audit[-_MAX_AUDIT:]


def append_audit(
    case_id: str,
    event: str,
    *,
    actor: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    entry = AuditEvent(
        ts=_now(),
        event=event,
        actor=actor,
        detail=detail or {},
    )

    def _mutate(overlay: dict[str, Any]) -> None:
        audit = list(overlay.get("audit") or [])
        audit.append(entry.model_dump())
        overlay["audit"] = _trim_audit(audit)

    update_overlay(case_id, _mutate)
    return entry


def set_hypothesis(
    case_id: str,
    hypothesis: MatchHypothesis,
    *,
    raw: bool = False,
) -> None:
    """Persist hypothesis. When raw=True, also snapshot as raw_hypothesis."""

    def _mutate(overlay: dict[str, Any]) -> None:
        dumped = hypothesis.model_dump()
        overlay["hypothesis"] = dumped
        overlay["confidence_band"] = hypothesis.confidence_band
        overlay["citation_map"] = [c.model_dump() for c in hypothesis.citation_map]
        if raw or overlay.get("raw_hypothesis") is None:
            overlay["raw_hypothesis"] = dumped

    update_overlay(case_id, _mutate)


def set_summary(case_id: str, summary: InvestigationSummary) -> None:
    def _mutate(overlay: dict[str, Any]) -> None:
        overlay["summary"] = summary.model_dump()

    update_overlay(case_id, _mutate)


def set_guidance(case_id: str, guidance: ApplyGuidancePacket) -> None:
    def _mutate(overlay: dict[str, Any]) -> None:
        overlay["guidance"] = guidance.model_dump()

    update_overlay(case_id, _mutate)


def persist_investigation(
    case_id: str,
    *,
    hypothesis: MatchHypothesis,
    summary: InvestigationSummary,
    actor: str | None,
    audit_detail: dict[str, Any],
) -> None:
    """One overlay write for investigate: hypothesis + summary + audit event."""

    def _mutate(overlay: dict[str, Any]) -> None:
        dumped = hypothesis.model_dump()
        overlay["hypothesis"] = dumped
        overlay["raw_hypothesis"] = dumped
        overlay["confidence_band"] = hypothesis.confidence_band
        overlay["citation_map"] = [c.model_dump() for c in hypothesis.citation_map]
        overlay["summary"] = summary.model_dump()
        entry = AuditEvent(
            ts=_now(),
            event="investigate",
            actor=actor,
            detail=audit_detail,
        )
        audit = list(overlay.get("audit") or [])
        audit.append(entry.model_dump())
        overlay["audit"] = _trim_audit(audit)

    update_overlay(case_id, _mutate)


def persist_hypothesis_edit(
    case_id: str,
    *,
    hypothesis: MatchHypothesis,
    actor: str | None,
    audit_detail: dict[str, Any],
) -> None:
    """One overlay write for hypothesis edit + audit (keeps raw_hypothesis)."""

    def _mutate(overlay: dict[str, Any]) -> None:
        dumped = hypothesis.model_dump()
        overlay["hypothesis"] = dumped
        overlay["confidence_band"] = hypothesis.confidence_band
        overlay["citation_map"] = [c.model_dump() for c in hypothesis.citation_map]
        entry = AuditEvent(
            ts=_now(),
            event="hypothesis_edited",
            actor=actor,
            detail=audit_detail,
        )
        audit = list(overlay.get("audit") or [])
        audit.append(entry.model_dump())
        overlay["audit"] = _trim_audit(audit)

    update_overlay(case_id, _mutate)


def set_decision(
    case_id: str,
    *,
    decision: str,
    reason_code: str | None,
    actor: str | None = None,
    confidence_band: str | None = None,
    citation_map: list[dict[str, Any]] | None = None,
    raw_hypothesis: dict[str, Any] | None = None,
    edited_hypothesis: dict[str, Any] | None = None,
) -> None:
    def _mutate(overlay: dict[str, Any]) -> None:
        overlay["last_decision"] = decision
        overlay["reason_code"] = reason_code
        overlay["decision_actor"] = actor
        overlay["decision_at"] = _now()
        if confidence_band is not None:
            overlay["confidence_band"] = confidence_band
        if citation_map is not None:
            overlay["citation_map"] = citation_map
        if raw_hypothesis is not None:
            overlay["raw_hypothesis"] = raw_hypothesis
        if edited_hypothesis is not None:
            overlay["hypothesis"] = edited_hypothesis

    update_overlay(case_id, _mutate)


def persist_decision(
    case_id: str,
    *,
    decision: str,
    reason_code: str | None,
    actor: str | None,
    audit_detail: dict[str, Any],
    confidence_band: str | None = None,
    citation_map: list[dict[str, Any]] | None = None,
    raw_hypothesis: dict[str, Any] | None = None,
    edited_hypothesis: dict[str, Any] | None = None,
    guidance: ApplyGuidancePacket | None = None,
    hypothesis: MatchHypothesis | None = None,
) -> None:
    """One overlay write for decide: optional hyp/guidance + decision fields + audit."""

    def _mutate(overlay: dict[str, Any]) -> None:
        if hypothesis is not None:
            dumped = hypothesis.model_dump()
            overlay["hypothesis"] = dumped
            overlay["confidence_band"] = hypothesis.confidence_band
            overlay["citation_map"] = [c.model_dump() for c in hypothesis.citation_map]
            if overlay.get("raw_hypothesis") is None:
                overlay["raw_hypothesis"] = dumped
        if guidance is not None:
            overlay["guidance"] = guidance.model_dump()
        overlay["last_decision"] = decision
        overlay["reason_code"] = reason_code
        overlay["decision_actor"] = actor
        overlay["decision_at"] = _now()
        if confidence_band is not None:
            overlay["confidence_band"] = confidence_band
        if citation_map is not None:
            overlay["citation_map"] = citation_map
        if raw_hypothesis is not None:
            overlay["raw_hypothesis"] = raw_hypothesis
        if edited_hypothesis is not None:
            overlay["hypothesis"] = edited_hypothesis
        entry = AuditEvent(
            ts=_now(),
            event="decision",
            actor=actor,
            detail=audit_detail,
        )
        audit = list(overlay.get("audit") or [])
        audit.append(entry.model_dump())
        overlay["audit"] = _trim_audit(audit)

    update_overlay(case_id, _mutate)
