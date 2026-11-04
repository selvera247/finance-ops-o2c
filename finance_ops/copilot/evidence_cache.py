"""Short-TTL process cache for EvidencePack dumps (case open / investigate).

Invalidated on TTL expiry. Investigate seeds the cache so a follow-up
GET /evidence does not rebuild remittance/email packs.
"""

from __future__ import annotations

import os
import time
from typing import Any

from finance_ops.copilot.config import copilot_email_evidence_enabled

_TTL = float(os.getenv("COPILOT_EVIDENCE_CACHE_TTL_SEC", "45") or "45")
# key -> (expires_at_monotonic, pack_dict)
_CACHE: dict[tuple[str, str, bool, str], tuple[float, dict[str, Any]]] = {}


def _retriever_version() -> str:
    # Lazy import avoids circular import with investigate seeding this cache.
    from finance_ops.copilot.investigate import RETRIEVER_VERSION

    return RETRIEVER_VERSION


def _key(case_id: str, actor: str) -> tuple[str, str, bool, str]:
    return (
        case_id,
        actor or "api",
        copilot_email_evidence_enabled(),
        _retriever_version(),
    )


def get_cached_evidence(case_id: str, *, actor: str = "api") -> dict[str, Any] | None:
    if _TTL <= 0:
        return None
    k = _key(case_id, actor)
    hit = _CACHE.get(k)
    if not hit:
        return None
    expires, pack = hit
    if time.monotonic() > expires:
        _CACHE.pop(k, None)
        return None
    return pack


def cache_evidence_pack(
    case_id: str,
    *,
    actor: str,
    pack: dict[str, Any],
) -> None:
    if _TTL <= 0:
        return
    _CACHE[_key(case_id, actor)] = (time.monotonic() + _TTL, pack)


def invalidate_evidence(case_id: str | None = None) -> None:
    if case_id is None:
        _CACHE.clear()
        return
    for k in list(_CACHE):
        if k[0] == case_id:
            _CACHE.pop(k, None)


def cache_stats() -> dict[str, Any]:
    return {"entries": len(_CACHE), "ttl_sec": _TTL}
