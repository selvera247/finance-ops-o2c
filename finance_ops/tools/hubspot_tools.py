"""HubSpot CRM tools — read for specialists; write for HITL runtime path only.

Read tools: get_company, get_deal, list_closed_won_deals, get_deal_line_items,
get_open_tickets_for_company.
Write tools: create_task, create_note (not on coordinator/payments RBAC).
"""

from __future__ import annotations

from typing import Any

from finance_ops.integrations.hubspot_client import (
    HubSpotAPIError,
    HubSpotClient,
    HubSpotConfigError,
    get_client,
)
from finance_ops.lib.evidence import record_evidence
from finance_ops.runtime.circuit_breaker import CircuitOpenError
from finance_ops.runtime.sanitize import sanitize_for_export

# Properties we allow into agent-facing results (minimize PII surface).
_COMPANY_PROPS = [
    "name",
    "domain",
    "hs_object_id",
    "hubspot_owner_id",
    "lifecyclestage",
    "hs_lastmodifieddate",
]
_DEAL_PROPS = [
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "closedate",
    "hs_object_id",
    "hubspot_owner_id",
    "hs_is_closed_won",
]
_LINE_PROPS = ["name", "quantity", "price", "amount", "hs_sku", "hs_product_id"]
_TICKET_PROPS = ["subject", "hs_pipeline_stage", "hs_ticket_priority", "createdate", "hs_object_id"]


def _err(status: str, error: str, **extra: Any) -> dict[str, Any]:
    out = {"status": status, "error": error, "needs_review": True, **extra}
    return out


def _props(obj: dict[str, Any]) -> dict[str, Any]:
    raw = obj.get("properties") if isinstance(obj.get("properties"), dict) else {}
    return {k: v for k, v in raw.items() if v is not None}


def _client_or_error() -> HubSpotClient | dict[str, Any]:
    try:
        return get_client()
    except HubSpotConfigError as exc:
        return _err("denied", "hubspot_token_missing", detail=str(exc))


def get_company(company_id: str) -> dict[str, Any]:
    """Read a HubSpot company by id (minimal properties)."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    company_id = company_id.strip()
    if not company_id:
        return _err("error", "company_id required")
    try:
        raw = client.get_object("companies", company_id, properties=_COMPANY_PROPS)
        company = sanitize_for_export(
            {"id": raw.get("id"), "properties": _props(raw)}
        )
        result = {"status": "success", "company": company, "needs_review": False}
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="get_company",
            inputs={"company_id": company_id},
            outputs={"id": company.get("id")},
            sources=[f"hubspot:company:{company_id}"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)


def get_deal(deal_id: str) -> dict[str, Any]:
    """Read a HubSpot deal by id."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    deal_id = deal_id.strip()
    if not deal_id:
        return _err("error", "deal_id required")
    try:
        raw = client.get_object("deals", deal_id, properties=_DEAL_PROPS)
        deal = sanitize_for_export({"id": raw.get("id"), "properties": _props(raw)})
        result = {"status": "success", "deal": deal, "needs_review": False}
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="get_deal",
            inputs={"deal_id": deal_id},
            outputs={"id": deal.get("id")},
            sources=[f"hubspot:deal:{deal_id}"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)


def list_closed_won_deals(
    company_id: str = "",
    limit: int = 25,
) -> dict[str, Any]:
    """List closed-won deals, optionally filtered by associated company id via search."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    limit = max(1, min(int(limit), 50))
    filters: list[dict[str, Any]] = [
        {"propertyName": "hs_is_closed_won", "operator": "EQ", "value": "true"},
    ]
    # Company filter uses associations search when company_id provided — property associations
    # are not always searchable; if company_id set we still search closed-won then note filter.
    try:
        raw = client.search_objects(
            "deals",
            filter_groups=[{"filters": filters}],
            properties=_DEAL_PROPS,
            limit=limit,
        )
        results = []
        for row in raw.get("results") or []:
            results.append(
                sanitize_for_export({"id": row.get("id"), "properties": _props(row)})
            )
        # Optional post-filter hint when company_id supplied (full assoc filter in D5)
        result = {
            "status": "success",
            "count": len(results),
            "deals": results,
            "company_id": company_id.strip() or None,
            "needs_review": False,
        }
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="list_closed_won_deals",
            inputs={"company_id": company_id, "limit": limit},
            outputs={"count": len(results)},
            sources=["hubspot:deals:closed_won"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)


def get_deal_line_items(deal_id: str) -> dict[str, Any]:
    """Fetch line items associated with a deal."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    deal_id = deal_id.strip()
    if not deal_id:
        return _err("error", "deal_id required")
    try:
        assoc = client.list_associations("deals", deal_id, "line_items")
        ids: list[str] = []
        for row in assoc.get("results") or []:
            to_obj = row.get("toObjectId") or row.get("id")
            if to_obj is not None:
                ids.append(str(to_obj))
            # v4 shape: [{"toObjectId": ...}]
            for t in row.get("to") or []:
                if t.get("toObjectId") is not None:
                    ids.append(str(t["toObjectId"]))
        ids = list(dict.fromkeys(ids))
        items = []
        for lid in ids:
            raw = client.get_object("line_items", lid, properties=_LINE_PROPS)
            items.append(
                sanitize_for_export({"id": raw.get("id"), "properties": _props(raw)})
            )
        result = {
            "status": "success",
            "deal_id": deal_id,
            "count": len(items),
            "line_items": items,
            "needs_review": False,
        }
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="get_deal_line_items",
            inputs={"deal_id": deal_id},
            outputs={"count": len(items)},
            sources=[f"hubspot:deal:{deal_id}", "hubspot:line_items"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)


def get_open_tickets_for_company(company_id: str, limit: int = 25) -> dict[str, Any]:
    """List tickets associated with a company (open stages preferred when present)."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    company_id = company_id.strip()
    if not company_id:
        return _err("error", "company_id required")
    limit = max(1, min(int(limit), 50))
    try:
        assoc = client.list_associations("companies", company_id, "tickets")
        ids: list[str] = []
        for row in assoc.get("results") or []:
            to_obj = row.get("toObjectId") or row.get("id")
            if to_obj is not None:
                ids.append(str(to_obj))
            for t in row.get("to") or []:
                if t.get("toObjectId") is not None:
                    ids.append(str(t["toObjectId"]))
        ids = list(dict.fromkeys(ids))[:limit]
        tickets = []
        for tid in ids:
            raw = client.get_object("tickets", tid, properties=_TICKET_PROPS)
            tickets.append(
                sanitize_for_export({"id": raw.get("id"), "properties": _props(raw)})
            )
        result = {
            "status": "success",
            "company_id": company_id,
            "count": len(tickets),
            "tickets": tickets,
            "needs_review": False,
        }
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="get_open_tickets_for_company",
            inputs={"company_id": company_id, "limit": limit},
            outputs={"count": len(tickets)},
            sources=[f"hubspot:company:{company_id}", "hubspot:tickets"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)


def create_task(
    subject: str,
    body: str = "",
    owner_id: str = "",
    company_id: str = "",
    deal_id: str = "",
) -> dict[str, Any]:
    """Create a HubSpot task (HITL/exception handoff — not for coordinator/payments LLM)."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    subject = (subject or "").strip()
    if not subject:
        return _err("error", "subject required")
    props: dict[str, Any] = {
        "hs_task_subject": subject[:256],
        "hs_task_body": (body or "")[:4000],
        "hs_task_status": "NOT_STARTED",
        "hs_task_type": "TODO",
    }
    if owner_id.strip():
        props["hubspot_owner_id"] = owner_id.strip()
    try:
        raw = client.create_object("tasks", props)
        task_id = str(raw.get("id") or "")
        # Associations via v4 would be a follow-up; return ids for HITL to link
        result = {
            "status": "success",
            "task_id": task_id,
            "company_id": company_id.strip() or None,
            "deal_id": deal_id.strip() or None,
            "needs_review": False,
        }
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="create_task",
            inputs={
                "subject": subject[:80],
                "company_id": company_id,
                "deal_id": deal_id,
            },
            outputs={"task_id": task_id},
            sources=[f"hubspot:task:{task_id}"] if task_id else ["hubspot:task"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)


def create_note(
    body: str,
    company_id: str = "",
    deal_id: str = "",
) -> dict[str, Any]:
    """Create a HubSpot note (HITL path only — minimal write)."""
    client = _client_or_error()
    if isinstance(client, dict):
        return client
    body = (body or "").strip()
    if not body:
        return _err("error", "body required")
    props = {"hs_note_body": body[:8000]}
    try:
        raw = client.create_object("notes", props)
        note_id = str(raw.get("id") or "")
        result = {
            "status": "success",
            "note_id": note_id,
            "company_id": company_id.strip() or None,
            "deal_id": deal_id.strip() or None,
            "needs_review": False,
        }
        result["evidence"] = record_evidence(
            agent="hubspot",
            action="create_note",
            inputs={"company_id": company_id, "deal_id": deal_id, "body_len": len(body)},
            outputs={"note_id": note_id},
            sources=[f"hubspot:note:{note_id}"] if note_id else ["hubspot:note"],
        )
        return result
    except CircuitOpenError as exc:
        return _err("circuit_open", str(exc))
    except HubSpotAPIError as exc:
        return _err("error", str(exc), http_status=exc.status_code)
