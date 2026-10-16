from __future__ import annotations

from typing import Any

from data_plane import repository as repo
from finance_ops.lib.evidence import record_evidence


def lookup_customer_risk(customer_id: str) -> dict[str, Any]:
    """Lookup ML/feature-store style customer AR risk features."""
    customer_id = customer_id.strip().upper()
    rows = repo.customer_features(customer_id)
    if not rows:
        result = {
            "status": "not_found",
            "customer_id": customer_id,
            "needs_review": True,
            "hint": "Run scripts/run_e2e_data_to_ai.py to compute features.",
        }
    else:
        feat = {
            k: (str(v) if hasattr(v, "isoformat") else v) for k, v in rows[0].items()
        }
        result = {"status": "success", "features": feat, "needs_review": False}

    evidence = record_evidence(
        agent="invoice_agent",
        action="lookup_customer_risk",
        inputs={"customer_id": customer_id},
        outputs=result,
        sources=[repo.source_label() + ":customer_features"] if rows else [],
    )
    result["evidence"] = evidence
    return result
