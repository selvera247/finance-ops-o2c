from __future__ import annotations

import threading
import time

import pytest

from gui_connectors.agent.playwright_connector import download_bank_statement
from gui_connectors.ingest.statement_ingest import ingest_bank_statement_csv
from gui_connectors.mock_portal.server import serve
from pipelines.batch.ingest import ingest_batch


@pytest.fixture(scope="module")
def portal_server():
    httpd = serve("127.0.0.1", 8765)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.4)
    yield "http://127.0.0.1:8765/"
    httpd.shutdown()


def test_playwright_download_and_ingest(portal_server):
    ingest_batch(run_id="gui-test-batch")
    gui = download_bank_statement(portal_url=portal_server, headless=True)
    assert gui["status"] == "success", gui
    assert gui["downloaded_file"]
    assert "login_ok" in gui["steps"]
    assert any(s.startswith("downloaded:") for s in gui["steps"])

    ingest = ingest_bank_statement_csv(gui["downloaded_file"])
    assert ingest["status"] == "success"
    assert ingest["rows"] >= 3

    from data_plane import repository as repo

    rows = repo.bank_statements("ACC-1001")
    assert len(rows) >= 3
