from __future__ import annotations

from finance_ops.runtime.sandbox import run_calc, run_python
from finance_ops.tools.sandbox_tools import run_sandboxed_calc, run_sandboxed_python


def test_calc_amount_tolerance() -> None:
    out = run_calc(
        "abs(payment - invoice) <= max(1.0, invoice * 0.005)",
        {"payment": 1842.5, "invoice": 1842.5},
    )
    assert out["status"] == "success"
    assert out["result"] is True


def test_calc_rejects_attribute_and_imports() -> None:
    out = run_calc("__import__('os').system('echo x')", {})
    assert out["status"] in {"error", "denied"}


def test_calc_policy_wall() -> None:
    out = run_calc("apply_payment_match", {"apply_payment_match": 1})
    assert out["status"] == "denied"


def test_python_sum_lines() -> None:
    out = run_python(
        "RESULT = round(sum(inputs['lines']), 2)",
        {"lines": [100.0, 50.25, 12.0]},
    )
    assert out["status"] == "success"
    assert out["result"] == 162.25
    assert out.get("isolation") == "subprocess_python_-I"


def test_python_blocks_os_import() -> None:
    out = run_python("import os\nRESULT = os.getcwd()", {})
    assert out["status"] in {"error", "denied"}


def test_python_blocks_finance_ops_name() -> None:
    out = run_python("RESULT = 'finance_ops'", {})
    assert out["status"] == "denied"


def test_tool_wrappers_evidence() -> None:
    calc = run_sandboxed_calc("payment + 1", '{"payment": 10}')
    assert calc["status"] == "success"
    assert calc["result"] == 11
    assert "evidence_id" in calc["evidence"]

    py = run_sandboxed_python("RESULT = inputs['n'] * 2", '{"n": 21}')
    assert py["status"] == "success"
    assert py["result"] == 42
    assert "evidence_id" in py["evidence"]
