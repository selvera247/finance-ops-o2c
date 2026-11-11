"""Short-TTL process cache for EvidencePack dumps (case open / investigate).

Invalidated on TTL expiry. Investigate seeds the cache so a follow-up
GET /evidence does not rebuild remittance/email packs. Bounded by max entries
(LRU-ish: drop oldest insertion when over capacity).
"""

from __future__ import annotations

import os
import time
from typing import Any

from finance_ops.copilot.config import copilot_email_evidence_enabled

_TTL = float(os.getenv("COPILOT_EVIDENCE_CACHE_TTL_SEC", "45") or "45")
_MAX_ENTRIES = max(8, int(os.getenv("COPILOT_EVIDENCE_CACHE_MAX", "128") or "128"))
# key -> (expires_at_monotonic, pack_dict); insertion order ≈ LRU for eviction.
_CACHE: dict[tuple[str, str, bool, str], tuple[float, dict[str, Any]]] = {}
# Once-per-case evidence_retrieved audit until invalidate (cuts GET miss RMW).
_EVIDENCE_AUDITED: set[str] = set()


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


def _evict_expired_and_overflow() -> None:
    now = time.monotonic()
    expired = [k for k, (exp, _) in _CACHE.items() if now > exp]
    for k in expired:
        _CACHE.pop(k, None)
    while len(_CACHE) > _MAX_ENTRIES:
        _CACHE.pop(next(iter(_CACHE)), None)


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
    # Refresh insertion order for LRU-ish eviction.
    _CACHE.pop(k, None)
    _CACHE[k] = (expires, pack)
    return pack


def cache_evidence_pack(
    case_id: str,
    *,
    actor: str,
    pack: dict[str, Any],
) -> None:
    if _TTL <= 0:
        return
    k = _key(case_id, actor)
    _CACHE.pop(k, None)
    _CACHE[k] = (time.monotonic() + _TTL, pack)
    _evict_expired_and_overflow()


def invalidate_evidence(case_id: str | None = None) -> None:
    if case_id is None:
        _CACHE.clear()
        _EVIDENCE_AUDITED.clear()
        return
    for k in list(_CACHE):
        if k[0] == case_id:
            _CACHE.pop(k, None)
    _EVIDENCE_AUDITED.discard(case_id)


def mark_evidence_audited(case_id: str) -> bool:
    """Return True if this is the first audit mark since last invalidate."""
    if case_id in _EVIDENCE_AUDITED:
        return False
    _EVIDENCE_AUDITED.add(case_id)
    return True


def cache_stats() -> dict[str, Any]:
    return {
        "entries": len(_CACHE),
        "ttl_sec": _TTL,
        "max_entries": _MAX_ENTRIES,
    }
