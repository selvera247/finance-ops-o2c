# C7 — Sandboxed code exec

Untrusted agent-written math/code returns **data only**. Mutations stay on typed
tools + HITL (`request_cash_app_approval` / `decide_approval`).

## What shipped (A + B + D)

| Layer | Mechanism |
| --- | --- |
| **A Calc** | AST-whitelisted expressions (`run_sandboxed_calc`) |
| **B Python** | Subprocess `python -I` + empty env + temp cwd + restricted builtins (`run_sandboxed_python`) |
| **D Policy wall** | Blocklist scan; no `finance_ops` / write-tool names; guest cannot import warehouse packages; result JSON only |

**Not in MCP** — read-only MCP stays warehouse reads; sandbox is an ADK agent tool.

## Agent tools

```text
run_sandboxed_calc(expression, inputs_json="{}")
run_sandboxed_python(code, inputs_json="{}")   # assign RESULT = ...
```

Examples:

```python
# A — amount within 0.5%
run_sandboxed_calc(
    "abs(payment - invoice) <= max(1.0, invoice * 0.005)",
    '{"payment": 1842.5, "invoice": 1842.5}',
)

# B — remittance line sum
run_sandboxed_python(
    "RESULT = round(sum(inputs['lines']), 2)",
    '{"lines": [100.0, 50.25, 12.0]}',
)
```

Env: `FINANCE_OPS_SANDBOX_TIMEOUT` (seconds, default `2`).

## Follow-on — C (containers / gVisor)

A+B do **not** provide a full network/syscall jail. For customer-untrusted code in
prod, wrap the same worker in Docker/gVisor (or Cloud Run Jobs) with:

- no network egress  
- read-only rootfs + mounted scratch  
- CPU/memory limits  
- same policy wall (D) unchanged  

Track as **C7-C** when promoting beyond demo.

## Threat model (honest)

| Threat | A+B+D |
| --- | --- |
| `apply_payment_match` from guest | Blocked (no imports / no handles) |
| Read `.env` / ADC via `os` | Blocked in worker |
| Infinite loop | Timeout |
| Outbound HTTP | **Not fully blocked** without C |
| Host escape | **Not** claimed without C |
