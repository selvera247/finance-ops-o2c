"""Stable exception identifiers derived from lane + source."""

from __future__ import annotations


def exception_id(lane: str, source_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in source_id.upper())
    return f"EXE-{lane[:12]}-{safe[:40]}"


def lane_prefix(lane: str) -> str:
    """Map product lane to exception_id prefix segment."""
    if lane == "portal_remittance":
        return "portal"
    if lane == "hubspot_gap":
        return "hubspot"
    return "cash_app"
