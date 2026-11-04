"""Gold-set loader for Copilot scoreboard (Spike A / fixture cases)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

GOLD_PATH = Path(__file__).with_name("gold.yaml")


@dataclass
class GoldExpect:
    should_abstain: bool = False
    gold_invoice_ids: list[str] = field(default_factory=list)
    gold_amounts: list[float] = field(default_factory=list)
    amount_tolerance: float = 0.01
    required_source_types: list[str] = field(default_factory=list)
    allow_amount_from_payment: bool = False
    thin_evidence: bool = False


@dataclass
class GoldCase:
    id: str
    payment_id: str
    customer_id: str | None
    notes: str
    expect: GoldExpect
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoldSet:
    version: str
    source: str
    targets: dict[str, float]
    cases: list[GoldCase]


def _parse_expect(raw: dict[str, Any] | None) -> GoldExpect:
    data = raw or {}
    return GoldExpect(
        should_abstain=bool(data.get("should_abstain", False)),
        gold_invoice_ids=[str(x) for x in (data.get("gold_invoice_ids") or [])],
        gold_amounts=[float(x) for x in (data.get("gold_amounts") or [])],
        amount_tolerance=float(data.get("amount_tolerance") or 0.01),
        required_source_types=[str(x) for x in (data.get("required_source_types") or [])],
        allow_amount_from_payment=bool(data.get("allow_amount_from_payment", False)),
        thin_evidence=bool(data.get("thin_evidence", False)),
    )


def load_gold_cases(path: Path | None = None) -> GoldSet:
    gold_path = path or GOLD_PATH
    data = yaml.safe_load(gold_path.read_text(encoding="utf-8")) or {}
    cases: list[GoldCase] = []
    for row in data.get("cases") or []:
        cases.append(
            GoldCase(
                id=str(row["id"]),
                payment_id=str(row["payment_id"]).strip().upper(),
                customer_id=(str(row["customer_id"]) if row.get("customer_id") else None),
                notes=str(row.get("notes") or ""),
                expect=_parse_expect(row.get("expect")),
                raw=dict(row),
            )
        )
    return GoldSet(
        version=str(data.get("version") or "unknown"),
        source=str(data.get("source") or ""),
        targets={str(k): float(v) for k, v in (data.get("targets") or {}).items()},
        cases=cases,
    )
