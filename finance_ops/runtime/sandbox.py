"""C7 sandboxed execution: calc expressions (A) + isolated Python (B) + policy wall (D).

Policy (D): sandboxed code never receives write-tool handles, credentials, or
``finance_ops`` / ``data_plane`` imports. It may only return numbers / tables;
typed agent tools + HITL remain the only mutation path.

Container / gVisor isolation (C) is a follow-on — see docs/sandbox.md.
"""

from __future__ import annotations

import ast
import json
import operator
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Soft ceiling so agents cannot dump huge scripts into the tool.
_MAX_CODE_CHARS = 8_000
_DEFAULT_TIMEOUT_S = 2.0

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}
_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_ALLOWED_CALLS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "float": float,
    "int": int,
}

_POLICY_BLOCKLIST = (
    "finance_ops",
    "data_plane",
    "apply_payment_match",
    "decide_approval",
    "request_approval",
    "subprocess",
    "os.environ",
    "open(",
    "__import__",
)


def _timeout_s() -> float:
    raw = os.environ.get("FINANCE_OPS_SANDBOX_TIMEOUT", "")
    try:
        return max(0.25, float(raw)) if raw else _DEFAULT_TIMEOUT_S
    except ValueError:
        return _DEFAULT_TIMEOUT_S


def _policy_scan(code: str) -> str | None:
    lowered = code.lower()
    for needle in _POLICY_BLOCKLIST:
        if needle.lower() in lowered:
            return f"policy wall blocked pattern: {needle}"
    return None


class _SafeCalc(ast.NodeVisitor):
    """Evaluate a pure arithmetic / comparison expression against ``names``."""

    def __init__(self, names: dict[str, Any]) -> None:
        self.names = names

    def visit(self, node: ast.AST) -> Any:  # type: ignore[override]
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, bool, str)) or node.value is None:
                return node.value
            raise ValueError(f"constant type not allowed: {type(node.value).__name__}")
        if isinstance(node, ast.Name):
            if node.id not in self.names:
                raise ValueError(f"unknown name: {node.id}")
            return self.names[node.id]
        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError("operator not allowed")
            return op(self.visit(node.left), self.visit(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError("unary operator not allowed")
            return op(self.visit(node.operand))
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                val: Any = True
                for v in node.values:
                    val = self.visit(v)
                    if not val:
                        return val
                return val
            if isinstance(node.op, ast.Or):
                val = False
                for v in node.values:
                    val = self.visit(v)
                    if val:
                        return val
                return val
            raise ValueError("bool operator not allowed")
        if isinstance(node, ast.Compare):
            left = self.visit(node.left)
            for op_node, comparator in zip(node.ops, node.comparators):
                op = _CMP_OPS.get(type(op_node))
                if op is None:
                    raise ValueError("comparison not allowed")
                right = self.visit(comparator)
                if not op(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
                raise ValueError("function call not allowed")
            if node.keywords:
                raise ValueError("keyword args not allowed in calc")
            fn = _ALLOWED_CALLS[node.func.id]
            return fn(*(self.visit(a) for a in node.args))
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.visit(elt) for elt in node.elts]
        if isinstance(node, ast.Dict):
            return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values) if k is not None}
        raise ValueError(f"expression node not allowed: {type(node).__name__}")


def run_calc(expression: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """A — evaluate a safe arithmetic expression; ``inputs`` bind as names."""
    expression = (expression or "").strip()
    inputs = dict(inputs or {})
    if not expression:
        return {"status": "error", "mode": "calc", "error": "empty expression", "needs_review": True}
    if len(expression) > _MAX_CODE_CHARS:
        return {"status": "error", "mode": "calc", "error": "expression too long", "needs_review": True}
    blocked = _policy_scan(expression)
    if blocked:
        return {"status": "denied", "mode": "calc", "error": blocked, "needs_review": True, "policy": "D"}
    try:
        tree = ast.parse(expression, mode="eval")
        value = _SafeCalc(inputs).visit(tree)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "mode": "calc",
            "error": str(exc),
            "needs_review": True,
        }
    return {
        "status": "success",
        "mode": "calc",
        "result": value,
        "needs_review": False,
        "policy": "no_side_effects",
    }


def run_python(code: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """B — run short Python in a stripped subprocess (``python -I``).

    Guest code should assign ``RESULT = ...`` (or ``result``). Only JSON-serializable
    values are returned. No network jail without containers (C).
    """
    code = code or ""
    inputs = dict(inputs or {})
    if not code.strip():
        return {"status": "error", "mode": "python", "error": "empty code", "needs_review": True}
    if len(code) > _MAX_CODE_CHARS:
        return {"status": "error", "mode": "python", "error": "code too long", "needs_review": True}
    blocked = _policy_scan(code)
    if blocked:
        return {"status": "denied", "mode": "python", "error": blocked, "needs_review": True, "policy": "D"}

    worker_src = (Path(__file__).resolve().parent / "sandbox_worker.py").read_text(encoding="utf-8")
    payload = json.dumps({"code": code, "inputs": inputs}, default=str)
    timeout = _timeout_s()

    with tempfile.TemporaryDirectory(prefix="fo_sandbox_") as tmp:
        worker = Path(tmp) / "worker.py"
        worker.write_text(worker_src, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(worker)],
                input=payload,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                env={},  # empty env; -I ignores PYTHONPATH
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "mode": "python",
                "error": f"exceeded {timeout}s",
                "needs_review": True,
                "policy": "D",
            }
        except OSError as exc:
            return {
                "status": "error",
                "mode": "python",
                "error": f"spawn failed: {exc}",
                "needs_review": True,
            }

    if not proc.stdout.strip():
        return {
            "status": "error",
            "mode": "python",
            "error": proc.stderr.strip() or f"empty stdout (exit {proc.returncode})",
            "needs_review": True,
        }
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "mode": "python",
            "error": f"worker non-json: {proc.stdout[:400]}",
            "stderr": proc.stderr[:400] if proc.stderr else "",
            "needs_review": True,
        }
    if not body.get("ok"):
        return {
            "status": "error",
            "mode": "python",
            "error": body.get("error", "worker failed"),
            "needs_review": True,
            "policy": "D",
        }
    return {
        "status": "success",
        "mode": "python",
        "result": body.get("result"),
        "needs_review": False,
        "policy": "no_side_effects",
        "isolation": "subprocess_python_-I",
        "note": "Container/gVisor (C) not enabled; use for trusted agent calc only.",
    }
