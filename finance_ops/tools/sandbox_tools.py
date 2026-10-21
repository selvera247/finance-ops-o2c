"""Agent tools for C7 sandboxed calc / Python (read-results only)."""

from __future__ import annotations

import json
from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.runtime.circuit_breaker import DEFAULT_BREAKER
from finance_ops.runtime.sandbox import run_calc, run_python


def _guard(tool_name: str) -> None:
    DEFAULT_BREAKER.record_tool(tool_name)


def _parse_inputs(inputs_json: str) -> dict[str, Any]:
    raw = (inputs_json or "").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("inputs_json must be a JSON object")
    return data


def run_sandboxed_calc(expression: str, inputs_json: str = "{}") -> dict[str, Any]:
    """C7-A: evaluate a safe arithmetic expression (abs/round/min/max/sum/...).

    Bind variables via inputs_json, e.g. '{"payment":1842.5,"invoice":1842.5}'.
    Returns numbers/bools only — cannot apply matches or call other tools.
    """
    _guard("run_sandboxed_calc")
    try:
        inputs = _parse_inputs(inputs_json)
    except (json.JSONDecodeError, ValueError) as exc:
        result: dict[str, Any] = {
            "status": "error",
            "mode": "calc",
            "error": str(exc),
            "needs_review": True,
        }
        result["evidence"] = record_evidence(
            agent="sandbox",
            action="run_sandboxed_calc",
            inputs={"expression": expression, "inputs_json": inputs_json},
            outputs=result,
            sources=["sandbox:calc"],
        )
        return result

    result = run_calc(expression, inputs)
    result["evidence"] = record_evidence(
        agent="sandbox",
        action="run_sandboxed_calc",
        inputs={"expression": expression, "inputs": inputs},
        outputs={"status": result.get("status"), "result": result.get("result"), "error": result.get("error")},
        sources=["sandbox:calc", "policy:D"],
    )
    return result


def run_sandboxed_python(code: str, inputs_json: str = "{}") -> dict[str, Any]:
    """C7-B: run short Python in an isolated ``python -I`` subprocess.

    Assign RESULT = ... in the guest code. ``inputs`` is injected as a dict.
    Policy wall (D): no finance_ops imports, no apply/HITL, no open/os/subprocess.
    Does not apply payment matches — use request_cash_app_approval for writes.
    """
    _guard("run_sandboxed_python")
    try:
        inputs = _parse_inputs(inputs_json)
    except (json.JSONDecodeError, ValueError) as exc:
        result = {
            "status": "error",
            "mode": "python",
            "error": str(exc),
            "needs_review": True,
        }
        result["evidence"] = record_evidence(
            agent="sandbox",
            action="run_sandboxed_python",
            inputs={"code_len": len(code or ""), "inputs_json": inputs_json},
            outputs=result,
            sources=["sandbox:python"],
        )
        return result

    result = run_python(code, inputs)
    result["evidence"] = record_evidence(
        agent="sandbox",
        action="run_sandboxed_python",
        inputs={"code_len": len(code), "inputs_keys": sorted(inputs.keys())},
        outputs={
            "status": result.get("status"),
            "result": result.get("result"),
            "error": result.get("error"),
            "isolation": result.get("isolation"),
        },
        sources=["sandbox:python", "policy:D"],
    )
    return result
