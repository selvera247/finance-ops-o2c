"""C5 — sanitize payloads before evidence, Slack, MCP, and logs.

Redacts secrets and obvious credential-shaped strings. Keeps business ids
(INV-*, PAY-*, CUST-*, C-*) intact.
"""

from __future__ import annotations

import re
from typing import Any

_REDACT = "[REDACTED]"

# Env-style and bearer secrets
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|webhook|"
    r"private[_-]?key|access[_-]?key|refresh[_-]?token|client[_-]?secret|"
    r"slack_|google_|gemini_|aws_|bearer)",
    re.I,
)

# Long token-like literals (PATs, JWTs, slack tokens, hex secrets)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b("
    r"github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|Bearer\s+[A-Za-z0-9._\-+/=]{20,}"
    r"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9._-]{10,}"
    r"|AIza[0-9A-Za-z_-]{20,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|hooks\.slack\.com/services/[A-Za-z0-9/]+"
    r")"
)

# Optional account-ish digit runs (keep short refs; redact long digit strings)
_ACCOUNT_RE = re.compile(r"\b\d{12,19}\b")


def sanitize_string(text: str, *, redact_accounts: bool = True) -> str:
    if not text:
        return text
    out = _SECRET_VALUE_RE.sub(_REDACT, text)
    if redact_accounts:
        out = _ACCOUNT_RE.sub(_REDACT, out)
    return out


def sanitize_for_export(value: Any, *, redact_accounts: bool = True, _depth: int = 0) -> Any:
    """Deep-sanitize dict/list/str for export surfaces."""
    if _depth > 12:
        return _REDACT
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return sanitize_string(value, redact_accounts=redact_accounts)
    if isinstance(value, bytes):
        return _REDACT
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if _SECRET_KEY_RE.search(key_str):
                out[k] = _REDACT
            else:
                out[k] = sanitize_for_export(v, redact_accounts=redact_accounts, _depth=_depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize_for_export(v, redact_accounts=redact_accounts, _depth=_depth + 1) for v in value]
    return sanitize_string(str(value), redact_accounts=redact_accounts)
