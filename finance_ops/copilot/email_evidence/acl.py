"""Actor → customer_id allowlist. Fail closed on unknown actors / cross-customer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from finance_ops.lib.paths import REPO_ROOT

_DEFAULT_ACL = REPO_ROOT / "data" / "copilot" / "actor_acl.json"


def _acl_path() -> Path:
    override = (os.getenv("COPILOT_ACTOR_ACL_PATH") or "").strip()
    if override:
        return Path(override)
    return _DEFAULT_ACL


def load_actor_acl() -> dict[str, list[str]]:
    """Return mapping actor → list of customer_ids (or ['*'])."""
    path = _acl_path()
    if not path.is_file():
        return {}
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    actors = raw.get("actors") or {}
    out: dict[str, list[str]] = {}
    for actor, scopes in actors.items():
        if isinstance(scopes, list):
            out[str(actor).strip().lower()] = [str(s).strip() for s in scopes]
    # Env overlay: COPILOT_ACTOR_CUSTOMERS=pilot:C-1042,C-4417;other:C-2081
    env = (os.getenv("COPILOT_ACTOR_CUSTOMERS") or "").strip()
    if env:
        for part in env.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            name, rest = part.split(":", 1)
            key = name.strip().lower()
            scopes = [s.strip() for s in rest.split(",") if s.strip()]
            if scopes:
                out[key] = scopes
    return out


def actor_may_access_customer(actor: str | None, customer_id: str | None) -> bool:
    """Fail closed: missing actor/customer or unknown actor → False."""
    if not actor or not customer_id:
        return False
    acl = load_actor_acl()
    scopes = acl.get(str(actor).strip().lower())
    if not scopes:
        return False
    if "*" in scopes:
        return True
    return str(customer_id).strip().upper() in {s.upper() for s in scopes}


def filter_messages_for_customer(
    messages: list[Any],
    *,
    customer_id: str,
) -> list[Any]:
    """Drop any message whose customer_id does not exactly match (fail closed)."""
    want = str(customer_id).strip().upper()
    kept = []
    for msg in messages:
        cid = getattr(msg, "customer_id", None)
        if cid is None and isinstance(msg, dict):
            cid = msg.get("customer_id")
        if cid is None:
            continue
        if str(cid).strip().upper() == want:
            kept.append(msg)
    return kept
