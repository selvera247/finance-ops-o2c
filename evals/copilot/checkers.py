"""Copilot scoreboard checkers — citation, harmful-error, abstain calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from evals.copilot.gold import GoldCase, GoldSet


@dataclass
class CaseCheckResult:
    case_id: str
    payment_id: str
    citation_valid: bool
    harmful_error: bool
    abstain_calibrated: bool
    passed: bool
    notes: list[str] = field(default_factory=list)
    hypothesis_invoice_ids: list[str] = field(default_factory=list)
    confidence_band: str | None = None
    insufficient_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Scoreboard:
    version: str
    case_count: int
    citation_validity: float
    harmful_error_rate: float
    insufficient_calibration: float
    pass_rate: float
    passed: int
    failed: int
    targets: dict[str, float]
    targets_met: dict[str, bool]
    cases: list[CaseCheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "case_count": self.case_count,
            "citation_validity": self.citation_validity,
            "harmful_error_rate": self.harmful_error_rate,
            "insufficient_calibration": self.insufficient_calibration,
            "pass_rate": self.pass_rate,
            "passed": self.passed,
            "failed": self.failed,
            "targets": self.targets,
            "targets_met": self.targets_met,
            "cases": [c.to_dict() for c in self.cases],
        }


def _evidence_ids(evidence: dict[str, Any] | None) -> set[str]:
    items = (evidence or {}).get("items") or []
    return {str(i.get("source_id")) for i in items if i.get("source_id")}


def _evidence_types(evidence: dict[str, Any] | None) -> set[str]:
    items = (evidence or {}).get("items") or []
    return {str(i.get("source_type")) for i in items if i.get("source_type")}


def check_citation_validity(
    *,
    hypothesis: dict[str, Any],
    evidence: dict[str, Any] | None,
    gold: GoldCase,
) -> tuple[bool, list[str]]:
    """Every claim citation must point at a retrieved source id, or the draft abstains."""
    notes: list[str] = []
    if hypothesis.get("insufficient_data") or hypothesis.get("confidence_band") == "insufficient":
        # Abstain is a valid citation outcome (no rubber-stamped uncited claims).
        return True, notes

    source_ids = _evidence_ids(evidence)
    citations = list(hypothesis.get("citation_map") or [])
    if not citations:
        notes.append("no citation_map on non-abstain hypothesis")
        return False, notes

    missing: list[str] = []
    for cite in citations:
        sid = str(cite.get("source_id") or "")
        if not sid or sid not in source_ids:
            missing.append(sid or "<empty>")
    if missing:
        notes.append(f"citations missing from evidence: {missing}")
        return False, notes

    required = gold.expect.required_source_types
    if required:
        present = _evidence_types(evidence)
        absent = [t for t in required if t not in present]
        if absent:
            notes.append(f"missing required evidence source_types: {absent}")
            return False, notes

    # Lines should cite the proposed invoice ids when present.
    for line in hypothesis.get("lines") or []:
        inv = str(line.get("invoice_id") or "")
        if inv and inv not in source_ids and f"RULE-{inv}" not in source_ids:
            notes.append(f"line invoice {inv} not in evidence pack")
            return False, notes

    return True, notes


def check_harmful_error(
    *,
    hypothesis: dict[str, Any],
    gold: GoldCase,
) -> tuple[bool, list[str]]:
    """Would rubber-stamping the raw hypothesis post the wrong invoice/amount?

    Returns (is_harmful, notes). Stub definition: wrong invoice_id vs gold, or
    amount outside tolerance when gold amounts are labeled.
    """
    notes: list[str] = []
    if gold.expect.should_abstain:
        # Abstain gold: proposing a confident match is scored under calibration,
        # not as a cash-posting harmful error unless lines are present + not insufficient.
        if hypothesis.get("insufficient_data"):
            return False, notes
        if not (hypothesis.get("lines") or []):
            return False, notes
        # Soft: treating a forced proposal on abstain gold as potentially harmful
        # only when confidence is medium/high (would look accept-ready).
        band = str(hypothesis.get("confidence_band") or "")
        if band in {"medium", "high"}:
            notes.append("confident proposal on abstain gold — harmful if rubber-stamped")
            return True, notes
        return False, notes

    if hypothesis.get("insufficient_data") or not (hypothesis.get("lines") or []):
        # Abstaining when gold expects a match is not a harmful post — calibration.
        return False, notes

    gold_ids = {x.upper() for x in gold.expect.gold_invoice_ids}
    lines = list(hypothesis.get("lines") or [])
    hyp_ids = [str(ln.get("invoice_id") or "").upper() for ln in lines]
    if gold_ids and not any(i in gold_ids for i in hyp_ids):
        notes.append(f"wrong invoice if rubber-stamped: got {hyp_ids} gold={sorted(gold_ids)}")
        return True, notes

    if gold.expect.gold_amounts and not gold.expect.allow_amount_from_payment:
        tol = float(gold.expect.amount_tolerance)
        for ln, expected in zip(lines, gold.expect.gold_amounts):
            got = float(ln.get("amount") or 0)
            if abs(got - float(expected)) > tol:
                notes.append(
                    f"wrong amount if rubber-stamped: got {got} gold={expected} tol={tol}"
                )
                return True, notes

    return False, notes


def check_insufficient_calibration(
    *,
    hypothesis: dict[str, Any],
    gold: GoldCase,
) -> tuple[bool, list[str]]:
    """Abstain when gold says missing evidence; penalize false-confident drafts."""
    notes: list[str] = []
    insufficient = bool(hypothesis.get("insufficient_data"))
    band = str(hypothesis.get("confidence_band") or "")
    abstained = insufficient or band == "insufficient" or not (hypothesis.get("lines") or [])

    if gold.expect.should_abstain:
        # Accept low-confidence thin proposals only when explicitly thin_evidence
        # and band is low (still prefer abstain).
        if abstained:
            return True, notes
        if gold.expect.thin_evidence and band == "low":
            notes.append("thin evidence proposed at low confidence — acceptable calibration")
            return True, notes
        if band in {"medium", "high"}:
            notes.append("false-confident: gold expects abstain/insufficient")
            return False, notes
        notes.append("expected abstain but hypothesis has lines")
        return False, notes

    # Gold expects a match — abstaining is a calibration miss (not harmful).
    if abstained:
        notes.append("false abstain: gold expects a match hypothesis")
        return False, notes
    return True, notes


def check_case(
    gold: GoldCase,
    *,
    hypothesis: dict[str, Any],
    evidence: dict[str, Any] | None = None,
) -> CaseCheckResult:
    cite_ok, cite_notes = check_citation_validity(
        hypothesis=hypothesis, evidence=evidence, gold=gold
    )
    harmful, harm_notes = check_harmful_error(hypothesis=hypothesis, gold=gold)
    calib_ok, calib_notes = check_insufficient_calibration(
        hypothesis=hypothesis, gold=gold
    )
    notes = cite_notes + harm_notes + calib_notes
    lines = list(hypothesis.get("lines") or [])
    passed = cite_ok and (not harmful) and calib_ok
    return CaseCheckResult(
        case_id=gold.id,
        payment_id=gold.payment_id,
        citation_valid=cite_ok,
        harmful_error=harmful,
        abstain_calibrated=calib_ok,
        passed=passed,
        notes=notes,
        hypothesis_invoice_ids=[str(ln.get("invoice_id") or "") for ln in lines],
        confidence_band=hypothesis.get("confidence_band"),
        insufficient_data=bool(hypothesis.get("insufficient_data")),
    )


def summarize_scoreboard(
    gold_set: GoldSet,
    results: list[CaseCheckResult],
) -> Scoreboard:
    n = len(results) or 1
    citation_validity = sum(1 for r in results if r.citation_valid) / n
    harmful_error_rate = sum(1 for r in results if r.harmful_error) / n
    insufficient_calibration = sum(1 for r in results if r.abstain_calibrated) / n
    passed = sum(1 for r in results if r.passed)
    targets = dict(gold_set.targets)
    targets_met = {
        "citation_validity": citation_validity
        >= float(targets.get("citation_validity", 0.95)),
        "harmful_error_rate_max": harmful_error_rate
        <= float(targets.get("harmful_error_rate_max", 0.02)),
        "insufficient_calibration": insufficient_calibration
        >= float(targets.get("insufficient_calibration", 0.90)),
    }
    return Scoreboard(
        version=gold_set.version,
        case_count=len(results),
        citation_validity=round(citation_validity, 3),
        harmful_error_rate=round(harmful_error_rate, 3),
        insufficient_calibration=round(insufficient_calibration, 3),
        pass_rate=round(passed / n, 3) if results else 0.0,
        passed=passed,
        failed=len(results) - passed,
        targets=targets,
        targets_met=targets_met,
        cases=results,
    )
