"""SKU catalog — Free visibility vs paid resolve / retainer."""

from __future__ import annotations

from typing import Any

SKUS: dict[str, dict[str, Any]] = {
    "free.visibility": {
        "code": "free.visibility",
        "name": "AR visibility",
        "tier": "free",
        "pricing": "included",
        "unit": None,
        "includes": [
            "aging",
            "list exceptions",
            "MCP read",
            "HubSpot enrich (read)",
            "shadow proposals",
            "queue metrics",
        ],
        "bill_on": None,
    },
    "resolve.cash_app": {
        "code": "resolve.cash_app",
        "name": "Cash-app resolve",
        "tier": "paid",
        "pricing": "per_exception",
        "unit": "exception",
        "includes": [
            "request_cash_app_approval",
            "HITL",
            "apply_payment_match",
            "evidence",
        ],
        "bill_on": "resolved",
    },
    "resolve.portal": {
        "code": "resolve.portal",
        "name": "Portal remittance resolve",
        "tier": "paid",
        "pricing": "per_exception",
        "unit": "exception",
        "includes": ["portal HITL review", "evidence"],
        "bill_on": "resolved",
    },
    "retainer.ar_ops": {
        "code": "retainer.ar_ops",
        "name": "Human AR ops retainer",
        "tier": "paid",
        "pricing": "weekly_or_monthly",
        "unit": "retainer_week",
        "includes": ["judgment", "exceptions coaching", "escalations"],
        "bill_on": "manual",
    },
}


def list_skus() -> dict[str, Any]:
    return {
        "status": "success",
        "skus": list(SKUS.values()),
        "needs_review": False,
    }


def sku_for_lane(lane: str) -> str:
    lane = (lane or "").lower()
    if lane in {"portal_remittance", "portal"}:
        return "resolve.portal"
    if lane in {"hubspot_gap", "hubspot"}:
        return "resolve.cash_app"  # bill via resolve until dedicated SKU exists
    return "resolve.cash_app"
