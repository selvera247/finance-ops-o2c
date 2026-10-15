from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import list_evidence, load_evidence, record_evidence


def get_evidence(evidence_id: str) -> dict[str, Any]:
    """Retrieve a previously recorded evidence artifact by evidence_id."""
    record = load_evidence(evidence_id.strip())
    if not record:
        return {
            "status": "not_found",
            "evidence_id": evidence_id,
            "needs_review": True,
        }
    return {"status": "success", "evidence": record, "needs_review": False}


def recent_evidence(limit: int = 10) -> dict[str, Any]:
    """List recent evidence records for audit / AgentOps demos."""
    limit = max(1, min(int(limit), 50))
    records = list_evidence(limit=limit)
    return {
        "status": "success",
        "count": len(records),
        "evidence": records,
        "needs_review": False,
    }


def flag_for_human_review(
    reason: str,
    related_ids: str = "",
    severity: str = "medium",
) -> dict[str, Any]:
    """Create an explicit human-review flag with governance metadata."""
    severity = severity.lower().strip()
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    result = {
        "status": "flagged",
        "reason": reason,
        "related_ids": [x.strip() for x in related_ids.split(",") if x.strip()],
        "severity": severity,
        "needs_review": True,
    }
    evidence = record_evidence(
        agent="coordinator",
        action="flag_for_human_review",
        inputs={
            "reason": reason,
            "related_ids": related_ids,
            "severity": severity,
        },
        outputs=result,
        sources=["governance:manual_flag"],
    )
    result["evidence"] = evidence
    return result
