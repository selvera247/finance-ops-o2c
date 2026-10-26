"""Append-only governance audit log (JSONL)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_plane.config import WAREHOUSE_DIR, ensure_dirs

_AUDIT_REL = Path("governance") / "audit.jsonl"


def audit_path() -> Path:
    ensure_dirs()
    root = WAREHOUSE_DIR / "governance"
    root.mkdir(parents=True, exist_ok=True)
    return WAREHOUSE_DIR / _AUDIT_REL


def args_hash(args: dict[str, Any] | None) -> str:
    raw = json.dumps(args or {}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def append_audit(
    *,
    event: str,
    agent: str,
    decision: str,
    tool: str | None = None,
    args: dict[str, Any] | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one structured audit record. Failures are swallowed after best-effort write."""
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "agent": agent,
        "tool": tool,
        "args_hash": args_hash(args),
        "decision": decision,
        "reason": reason,
    }
    if extra:
        record["extra"] = extra
    try:
        path = audit_path()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except OSError:
        record["audit_write_error"] = True
    return record
