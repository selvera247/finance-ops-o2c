# Copilot UI component layer

Production workbench UI for the Cash-Application Exception Copilot. Vanilla ES modules + CSS custom properties — **no bundler**, served from FastAPI next to `/v1/copilot/*`.

Guidance-only apply remains the happy path. API contracts are unchanged.

## Run the UI

```bash
# optional manual seed (Sync + refresh also auto-seeds the demo pack when
# the warehouse is empty/incomplete — needed on ephemeral Cloud Run)
PYTHONPATH=. python -c "from pipelines.batch.ingest import ingest_batch; ingest_batch()"
PYTHONPATH=. python scripts/load_spike_a.py --replace-customers

uvicorn finance_ops.serving:app --host 0.0.0.0 --port 8080
```

Demo packs (`COPILOT_DEMO_SEED_PACK`, default `base+spike_a`):

| Pack | Contents |
| --- | --- |
| `base` | `data/*.json` via ingest/bootstrap — `PAY-9002` / `PAY-9003` |
| `spike_a` | `data/spike_a` CSVs — `PAY-1001` / `PAY-2001` / … |
| `base+spike_a` | both (prior workbench queue shape) |

Spike B (`data/spike_b`) is portal remittance (`CLM-B*`), not cash_app. Set `COPILOT_AUTO_SEED=0` to disable Sync-time seeding. Blank `localStorage.FINANCE_OPS_API_TOKEN` is ignored (does not send `Bearer `).

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8080/copilot | Live workbench (queue → investigate → decide) |
| http://127.0.0.1:8080/copilot/examples | Story fixtures (empty / loading / error / ready) |
| http://127.0.0.1:8080/copilot-static/ | CSS + JS modules |
| http://127.0.0.1:8080/copilot/legacy | Previous single-file shell |
| http://127.0.0.1:8080/docs | OpenAPI |

Query helpers on the workbench:

- `?actor=pilot` — evidence ACL actor
- `?digest=1` — show DigestPreview (dry-run via `GET /v1/copilot/digest?force=true`)
- `?token=…` or `localStorage.FINANCE_OPS_API_TOKEN` — write token when writes are locked

## Architecture

```text
finance_ops/web/copilot/
  index.html              # /copilot entry
  examples.html           # /copilot/examples
  css/
    tokens.css            # design tokens (CSS variables)
    base.css              # shell layout, focus, skip link
    components.css        # component styles
  js/
    types.js              # JSDoc contracts (mirror types.py)
    utils.js              # esc, announce, Component base, reason codes
    api.js                # CopilotApi — explicit baseUrl/token, no globals
    fixtures.js           # example fixtures
    workbench.js          # composes components against live APIs
    examples.js           # story page
    components/
      shared.js           # Button, Text*, Select, Banner, Spinner, Skeleton, Modal, StatusPill
      ExceptionQueue.js
      CaseHeader.js
      EvidencePane.js
      HypothesisDraft.js
      ActionBar.js
      GuidancePacketView.js
      AuditTimeline.js
      DigestPreview.js
      index.js
```

**Composition model**

1. Each component is a small class: `new X(rootEl, props)` + `update(partialProps)`.
2. Props are explicit — `loading`, `error`, `disabled`, `ariaLabel` — never read from `window`.
3. The workbench owns fetch/state; components are presentational + emit callbacks (`onSelect`, `onDecision`, …).
4. Design tokens live in CSS variables (`--copilot-*`). Components use class names only.

Serving (`finance_ops/serving.py`):

- `GET /copilot` → `index.html`
- `GET /copilot/examples` → `examples.html`
- `StaticFiles` mount at `/copilot-static` → `finance_ops/web/copilot/`

## Component list

| Component | Role | Critical states |
| --- | --- | --- |
| **ExceptionQueue** | Ranked case listbox | empty / loading / error / ready |
| **CaseHeader** | Case id + StatusPill(s) | empty / loading / error / ready / insufficient |
| **EvidencePane** | Items by `source_type`; `#ev-{id}` jump targets | empty / thin / loading / error / ready |
| **HypothesisDraft** | Editable lines + notes + citation chips | insufficient banner / failed investigate / ready |
| **ActionBar** | Investigate, Accept, Edit&ready, Reject, Escalate, Need-info | Accept disabled when abstain; reason selects; confirm Modal |
| **GuidancePacketView** | ApplyGuidancePacket + copy text | empty / ready (guidance-only messaging) |
| **AuditTimeline** | Chronological audit events | empty / loading / ready |
| **DigestPreview** | Optional digest | **off-by-default** messaging / enabled / empty gates |
| **StatusPill** | Status / confidence chip | open, ready_to_apply, need_info, escalated, insufficient, … |
| **Button / TextInput / TextArea / Select** | Form primitives | disabled, error, aria-invalid |
| **Banner** | Info / success / warn / danger | `role=alert` on warn/danger |
| **Spinner / Skeleton** | Loading affordances | `aria-busy`, `role=status` |
| **Modal** | Confirmations | focus dialog, Escape / backdrop cancel |

## Accessibility

- Skip link → case detail
- Focus-visible rings on interactive controls
- Queue uses `role="listbox"` / `option` + `aria-selected`
- Evidence items are focusable citation targets (`tabindex="-1"`)
- Status updates via `aria-live` region (`announce()`)
- Action confirmations in a modal; **Escape** closes
- Insufficient-data banner uses `role="status"` / alert styling and disables Accept

## Edge cases covered in examples + workbench

| Case | Behavior |
| --- | --- |
| Empty queue | Empty status copy + Sync CTA |
| Failed investigate | ActionBar / HypothesisDraft error banner |
| Abstain / insufficient | Banner + Accept disabled |
| Thin evidence | EvidencePane warn banner |
| Cross-customer deny | CaseHeader / detail error surfaced assertively |
| Digest off | DigestPreview explains default-off policy |

## Tests

```bash
PYTHONPATH=. pytest tests/test_copilot_ui.py -q
```

Smoke coverage: routes + static assets, critical `aria-*` / `data-state` attributes in examples markup and component source, workbench mounts module scripts.

## Related

- Product / API: [copilot-mvp.md](./copilot-mvp.md)
- Backend: `finance_ops/copilot/`
