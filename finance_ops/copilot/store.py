"""File-backed Copilot case overlays (hypothesis, audit, guidance).

Exception projection stays in ar_exceptions; this store holds Copilot-specific
state so we do not break existing queue schema.

Discovery-minimum audit fields live on investigate/decision events and on the
overlay document (raw + edited hypothesis, citations, actor, timestamps).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_ops.copilot.types import (
    ApplyGuidancePacket,
    AuditEvent,
    InvestigationSummary,
    MatchHypothesis,
)
from finance_ops.lib.paths import REPO_ROOT


def _root() -> Path:
    base = REPO_ROOT / ".copilot" / "cases"
    base.mkdir(parents=True, exist_ok=True)
    return base


def case_path(case_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in case_id)
    return _root() / f"{safe}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_overlay(case_id: str) -> dict[str, Any]:
    path = case_path(case_id)
    if not path.is_file():
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
    return json.loads(path.read_text(encoding="utf-8"))


def save_overlay(case_id: str, data: dict[str, Any]) -> dict[str, Any]:
    path = case_path(case_id)
    data = {**data, "case_id": case_id, "updated_at": _now()}
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return data


def append_audit(
    case_id: str,
    event: str,
    *,
    actor: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    overlay = load_overlay(case_id)
    entry = AuditEvent(
        ts=_now(),
        event=event,
        actor=actor,
        detail=detail or {},
    )
    audit = list(overlay.get("audit") or [])
    audit.append(entry.model_dump())
    overlay["audit"] = audit
    save_overlay(case_id, overlay)
    return entry


def set_hypothesis(
    case_id: str,
    hypothesis: MatchHypothesis,
    *,
    raw: bool = False,
) -> None:
    """Persist hypothesis. When raw=True, also snapshot as raw_hypothesis."""
    overlay = load_overlay(case_id)
    dumped = hypothesis.model_dump()
    overlay["hypothesis"] = dumped
    overlay["confidence_band"] = hypothesis.confidence_band
    overlay["citation_map"] = [c.model_dump() for c in hypothesis.citation_map]
    if raw or overlay.get("raw_hypothesis") is None:
        overlay["raw_hypothesis"] = dumped
    save_overlay(case_id, overlay)


def set_summary(case_id: str, summary: InvestigationSummary) -> None:
    overlay = load_overlay(case_id)
    overlay["summary"] = summary.model_dump()
    save_overlay(case_id, overlay)


def set_guidance(case_id: str, guidance: ApplyGuidancePacket) -> None:
    overlay = load_overlay(case_id)
    overlay["guidance"] = guidance.model_dump()
    save_overlay(case_id, overlay)


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
    overlay = load_overlay(case_id)
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
    save_overlay(case_id, overlay)
