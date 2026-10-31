"""Shared pytest fixtures — keep process-wide circuit breaker from poisoning later tests."""

from __future__ import annotations

import pytest

from finance_ops.runtime.circuit_breaker import DEFAULT_BREAKER


@pytest.fixture(autouse=True)
def _reset_circuit_breaker() -> None:
    DEFAULT_BREAKER.reset()
    DEFAULT_BREAKER.max_tool_calls = 25
    DEFAULT_BREAKER.max_depth = 8
    yield
    DEFAULT_BREAKER.reset()
    DEFAULT_BREAKER.max_tool_calls = 25
    DEFAULT_BREAKER.max_depth = 8
