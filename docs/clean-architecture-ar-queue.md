# AR queue — clean architecture

**Goal:** Separate concerns, increase modularity, reduce coupling — **behavior unchanged**.  
**Bounded context:** AR exception queue (sync → list/metrics → HITL → resolve/meter).

---

## Folder structure

```text
finance_ops/ar_queue/
├── domain/                 # Pure rules — no I/O
│   ├── statuses.py         # OPEN / TERMINAL statuses
│   ├── ids.py              # exception_id(lane, source)
│   ├── skus.py             # SKU catalog + sku_for_lane
│   ├── matching.py         # payment ↔ invoice scoring
│   ├── portal_classify.py  # portal extract disposition
│   ├── exception_rows.py   # row builders (cash / portal / hubspot)
│   └── serialize.py        # datetime → ISO helpers
├── ports/                  # Protocols (dependency inversion)
│   └── repositories.py     # ExceptionStore · PaymentCatalog · CachePort
├── application/            # Use cases (orchestrate domain + ports)
│   ├── sync.py             # upsert + sync_from_warehouse
│   ├── queries.py          # list / get / metrics
│   ├── lifecycle.py        # pending_hitl · resolve + meter
│   └── scoring.py          # score_payment_match · batch (catalog I/O)
└── adapters/               # Infrastructure
    ├── warehouse_exceptions.py
    ├── warehouse_payments.py
    └── ttl_cache.py
```

Legacy paths stay as **thin façades** so agents, MCP, HTTP, and tests keep working:

| Old import | Now |
| --- | --- |
| `finance_ops.services.queue_service` | re-exports `ar_queue.application` |
| `finance_ops.services.sku_catalog` | re-exports `ar_queue.domain.skus` |
| `finance_ops.tools.payment_tools` score\* | domain + application scoring |
| `finance_ops.tools.portal_spike_tools.classify_portal_row` | `ar_queue.domain.portal_classify` |

Prefer new code: `from finance_ops.ar_queue import sync_from_warehouse, list_exceptions, …`.

---

## Dependency rule

```text
  adapters ──▶ application ──▶ domain
      │              │
      └── ports ◀────┘   (application depends on protocols;
                           adapters implement them)
```

- **Domain** never imports DuckDB, FastAPI, ADK, Slack, or cache.
- **Application** may call adapters via defaults today; injectable `store` / `catalog` / `cache` kwargs keep tests and future Redis/BQ swaps clean.
- **Adapters** own SQL, `data_plane.repository`, and TTL LRU.
- **Edge** (`serving.py`, MCP, agent tools) stays outside — calls application or façades.

---

## Concerns separated

| Concern | Before (coupled) | After |
| --- | --- | --- |
| Match scoring | Inside `payment_tools` + warehouse | `domain.matching` |
| Portal classify | Inside tool module | `domain.portal_classify` |
| Exception persistence | Mixed in `queue_service` | `adapters.warehouse_exceptions` |
| Sync orchestration | Same mega-module | `application.sync` |
| Cache policy | Scattered | `adapters.ttl_cache` + query use cases |
| SKUs | `services/sku_catalog` | `domain.skus` |

---

## Unchanged behavior

- Same HTTP `/v1/ar/*` contract, tool names, HITL cash-app path.
- Same exception IDs, SKU codes, scoring weights, portal dispositions.
- Same cache key prefixes (`ar:exceptions:list:…`, `ar:metrics:v1`, `ar:match:…`).
- Façades preserve public function signatures used by tests and durable DAG.

---

## Related

- Product: [ar-exception-queue.md](ar-exception-queue.md)
- System design: [architecture-ar-queue.md](architecture-ar-queue.md)
- Perf: [performance-ar-queue.md](performance-ar-queue.md)
