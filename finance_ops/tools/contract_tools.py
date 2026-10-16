from __future__ import annotations

from typing import Any

from data_plane import repository as repo
from finance_ops.lib.evidence import record_evidence


def lookup_contract(contract_id: str) -> dict[str, Any]:
    """Look up a contract by contract_id (e.g. CTR-2201)."""
    contract_id = contract_id.strip().upper()
    match = repo.get_contract(contract_id)
    if not match:
        result = {
            "status": "not_found",
            "contract_id": contract_id,
            "needs_review": True,
        }
    else:
        result = {
            "status": "success",
            "contract": {
                k: (str(v) if hasattr(v, "isoformat") else v) for k, v in match.items()
            },
            "needs_review": False,
        }

    evidence = record_evidence(
        agent="contracts_agent",
        action="lookup_contract",
        inputs={"contract_id": contract_id},
        outputs=result,
        sources=[repo.source_label()] if match else [],
    )
    result["evidence"] = evidence
    return result


def lookup_customer_contract(customer_id: str) -> dict[str, Any]:
    """Find active contract(s) for a customer_id."""
    customer_id = customer_id.strip().upper()
    rows = repo.list_contracts(customer_id=customer_id, active_only=True)
    clean = [
        {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}
        for row in rows
    ]
    result = {
        "status": "success" if clean else "not_found",
        "customer_id": customer_id,
        "contracts": clean,
        "needs_review": len(clean) == 0,
    }
    evidence = record_evidence(
        agent="contracts_agent",
        action="lookup_customer_contract",
        inputs={"customer_id": customer_id},
        outputs={"count": len(clean)},
        sources=[repo.source_label()],
    )
    result["evidence"] = evidence
    return result
