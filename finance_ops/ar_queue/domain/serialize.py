"""Row serialization helpers shared by domain scoring / projections."""

from __future__ import annotations

from typing import Any


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce datetimes to ISO strings for JSON-safe tool/API payloads."""
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}
