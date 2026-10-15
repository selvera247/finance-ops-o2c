from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.lib.fixtures import contracts


def lookup_contract(contract_id: str) -> dict[str, Any]:
    """Look up a contract by contract_id (e.g. CTR-2201)."""
    contract_id = contract_id.strip().upper()
    match = next((c for c in contracts() if c["contract_id"] == contract_id), None)
    if not match:
        result = {
            "status": "not_found",
            "contract_id": contract_id,
            "needs_review": True,
        }
    else:
        result = {"status": "success", "contract": match, "needs_review": False}

    evidence = record_evidence(
        agent="contracts_agent",
        action="lookup_contract",
        inputs={"contract_id": contract_id},
        outputs=result,
        sources=["fixture:contracts.json"] if match else [],
    )
    result["evidence"] = evidence
    return result


def lookup_customer_contract(customer_id: str) -> dict[str, Any]:
    """Find active contract(s) for a customer_id."""
    customer_id = customer_id.strip().upper()
    rows = [
        c
        for c in contracts()
        if c["customer_id"] == customer_id and c["status"] == "active"
    ]
    result = {
        "status": "success" if rows else "not_found",
        "customer_id": customer_id,
        "contracts": rows,
        "needs_review": len(rows) == 0,
    }
    evidence = record_evidence(
        agent="contracts_agent",
        action="lookup_customer_contract",
        inputs={"customer_id": customer_id},
        outputs={"count": len(rows)},
        sources=["fixture:contracts.json"],
    )
    result["evidence"] = evidence
    return result
