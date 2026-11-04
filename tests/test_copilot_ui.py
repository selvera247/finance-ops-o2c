"""Smoke / a11y attribute tests for the Copilot UI component layer."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.serving import app

UI_ROOT = Path(__file__).resolve().parents[1] / "finance_ops" / "web" / "copilot"
COMPONENTS = UI_ROOT / "js" / "components"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_copilot_workbench_serves_component_shell(client: TestClient) -> None:
    resp = client.get("/copilot")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    assert 'id="app"' in body
    assert 'data-copilot-workbench="1"' in body
    assert "/copilot-static/css/tokens.css" in body
    assert "/copilot-static/js/workbench.js" in body
    assert 'type="module"' in body


def test_copilot_examples_page(client: TestClient) -> None:
    resp = client.get("/copilot/examples")
    assert resp.status_code == 200
    body = resp.text
    assert 'data-copilot-examples="1"' in body
    assert "/copilot-static/js/examples.js" in body
    assert 'class="copilot-skip-link"' in body


def test_copilot_static_assets(client: TestClient) -> None:
    for path in (
        "/copilot-static/css/tokens.css",
        "/copilot-static/css/base.css",
        "/copilot-static/css/components.css",
        "/copilot-static/js/workbench.js",
        "/copilot-static/js/examples.js",
        "/copilot-static/js/components/ExceptionQueue.js",
        "/copilot-static/js/components/ActionBar.js",
        "/copilot-static/js/api.js",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert len(resp.content) > 50


def test_health_points_at_examples(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    data = health.json()
    assert data["self_serve"]["copilot"] == "/copilot"
    assert data["self_serve"]["copilot_examples"] == "/copilot/examples"
    assert data["copilot"]["examples"] == "/copilot/examples"


def test_design_tokens_define_copilot_vars() -> None:
    tokens = (UI_ROOT / "css" / "tokens.css").read_text(encoding="utf-8")
    for var in (
        "--copilot-bg",
        "--copilot-accent",
        "--copilot-ink",
        "--copilot-font",
        "--copilot-focus",
    ):
        assert var in tokens


@pytest.mark.parametrize(
    "filename,required",
    [
        (
            "ExceptionQueue.js",
            [
                'role: "listbox"',
                '"data-state": "loading"',
                '"data-state": "empty"',
                '"data-state": "error"',
                "aria-selected",
                "aria-busy",
            ],
        ),
        (
            "EvidencePane.js",
            [
                "ev-",
                '"data-state": "empty"',
                '"thin"',
                "Thin evidence",
                "aria-label",
            ],
        ),
        (
            "HypothesisDraft.js",
            [
                "Insufficient data",
                "insufficient",
                "cp-cite",
                "aria-label",
            ],
        ),
        (
            "ActionBar.js",
            [
                "Accept",
                "Edit & ready",
                "Reject",
                "Escalate",
                "Need info",
                "acceptDisabled",
                "reason-reject",
                "Modal",
            ],
        ),
        (
            "GuidancePacketView.js",
            ["Guidance only", "ApplyGuidancePacket", '"data-state": "empty"'],
        ),
        (
            "AuditTimeline.js",
            ['role: "status"', '"data-state": "empty"', "cp-audit"],
        ),
        (
            "DigestPreview.js",
            ["off by default", "disabled", "Digest"],
        ),
        (
            "shared.js",
            [
                "aria-invalid",
                "aria-modal",
                "aria-busy",
                'role: "dialog"',
                "cp-status-pill",
            ],
        ),
    ],
)
def test_component_a11y_and_state_markers(filename: str, required: list[str]) -> None:
    src = (COMPONENTS / filename).read_text(encoding="utf-8")
    for needle in required:
        assert needle in src, f"{filename} missing {needle!r}"


def test_component_barrel_exports() -> None:
    barrel = (COMPONENTS / "index.js").read_text(encoding="utf-8")
    for name in (
        "ExceptionQueue",
        "CaseHeader",
        "EvidencePane",
        "HypothesisDraft",
        "ActionBar",
        "GuidancePacketView",
        "AuditTimeline",
        "DigestPreview",
        "Button",
        "Modal",
        "Banner",
        "Spinner",
        "Skeleton",
    ):
        assert name in barrel


def test_examples_js_covers_edge_states() -> None:
    src = (UI_ROOT / "js" / "examples.js").read_text(encoding="utf-8")
    for needle in (
        "FIXTURE_CASE_ABSTAIN",
        "FIXTURE_CROSS_CUSTOMER_ERROR",
        "FIXTURE_DIGEST_OFF",
        "FIXTURE_EVIDENCE_THIN",
        "loading: true",
        "acceptDisabled: true",
    ):
        assert needle in src


def test_workbench_uses_live_api_client() -> None:
    src = (UI_ROOT / "js" / "workbench.js").read_text(encoding="utf-8")
    assert "CopilotApi" in src
    assert "aria-live" in src
    assert "cross_customer" in src
    assert "acceptDisabled" in src
    # No warehouse apply on happy path messaging
    assert "Guidance-only" in src or "guidance-only" in src.lower()


def test_jsdoc_types_mirror_decisions() -> None:
    types = (UI_ROOT / "js" / "types.js").read_text(encoding="utf-8")
    for decision in (
        "accept",
        "edit_ready_to_apply",
        "reject",
        "escalate",
        "need_info",
    ):
        assert decision in types


def test_reason_codes_aligned_with_backend() -> None:
    from finance_ops.copilot.reasons import REASON_CODES

    utils = (UI_ROOT / "js" / "utils.js").read_text(encoding="utf-8")
    for decision, codes in REASON_CODES.items():
        assert decision in utils
        for code in codes:
            assert code in utils


def test_legacy_shell_still_available(client: TestClient) -> None:
    resp = client.get("/copilot/legacy")
    assert resp.status_code == 200
    assert "Cash-App Exception Copilot" in resp.text


def test_no_implicit_api_globals_in_components() -> None:
    """Components must not call fetch/window APIs for Copilot data."""
    pattern = re.compile(r"\bfetch\s*\(")
    for path in COMPONENTS.glob("*.js"):
        if path.name == "index.js":
            continue
        src = path.read_text(encoding="utf-8")
        assert not pattern.search(src), f"{path.name} should not call fetch()"
