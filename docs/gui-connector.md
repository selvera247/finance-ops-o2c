# GUI Connector (Legacy Portal → Warehouse)

Enterprise finance systems often lack APIs. This module demonstrates a
**DOM-first Playwright agent** against a local mock bank portal, then ingests
the downloaded CSV into the Data→AI warehouse for `finance_ops` agents.

```text
Mock legacy portal (login → menus → CSV)
        │  Playwright (selectors + optional screenshot)
        ▼
   .downloads/*.csv
        │  statement_ingest
        ▼
 warehouse.bank_statements
        │
        ▼
 finance_ops tools (list_bank_statements / coordinator)
```

## Run

```bash
PYTHONPATH=. python scripts/run_gui_connector.py
# or separately:
PYTHONPATH=. python -m gui_connectors.mock_portal.server --port 8765
PYTHONPATH=. python -m gui_connectors.agent.playwright_connector
```

Demo credentials: `analyst` / `demo123`

## Design notes

- **DOM first** (`data-testid` selectors) for reliability.
- Screenshot captured on Statements page for Set-of-Mark / vision demos.
- No real bank credentials — mock portal only.
- Vision/SoM can be layered later where DOM fails (canvas, iframe hell).
