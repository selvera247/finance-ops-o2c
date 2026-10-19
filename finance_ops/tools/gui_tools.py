"""Agent-callable wrappers around the GUI connector (mock portal only)."""

from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import record_evidence


def fetch_legacy_bank_statement() -> dict[str, Any]:
    """Use Playwright to log into the mock legacy portal and ingest the CSV.

    Requires the mock portal to be running (scripts/run_gui_connector.py starts it).
    """
    from gui_connectors.agent.playwright_connector import download_bank_statement
    from gui_connectors.ingest.statement_ingest import ingest_bank_statement_csv

    gui = download_bank_statement()
    if gui.get("status") != "success" or not gui.get("downloaded_file"):
        result = {
            "status": "error",
            "gui": gui,
            "needs_review": True,
            "hint": "Start mock portal: PYTHONPATH=. python scripts/run_gui_connector.py",
        }
        result["evidence"] = record_evidence(
            agent="coordinator", action="fetch_legacy_bank_statement",
            inputs={}, outputs=result, sources=["gui:legacy_portal"],
        )
        return result

    ingest = ingest_bank_statement_csv(gui["downloaded_file"])
    result = {
        "status": "success" if ingest.get("status") == "success" else "error",
        "gui": gui,
        "ingest": ingest,
        "needs_review": False,
    }
    result["evidence"] = record_evidence(
        agent="coordinator", action="fetch_legacy_bank_statement",
        inputs={}, outputs={"rows": ingest.get("rows"), "file": gui.get("downloaded_file")},
        sources=["gui:legacy_portal", f"file:{gui.get('downloaded_file')}"],
    )
    return result


def list_bank_statements(account_id: str | None = None) -> dict[str, Any]:
    """List bank statement rows already ingested from the GUI connector."""
    from data_plane import repository as repo

    rows = repo.bank_statements(account_id)
    clean = [{k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in rows]
    result = {
        "status": "success", "count": len(clean), "statements": clean,
        "needs_review": len(clean) == 0,
    }
    result["evidence"] = record_evidence(
        agent="coordinator", action="list_bank_statements",
        inputs={"account_id": account_id}, outputs={"count": len(clean)},
        sources=[repo.source_label() + ":bank_statements"],
    )
    return result
