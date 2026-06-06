# Phase 10 — Docs & cutover  ✅ (sign-off pending)

## Parity sign-off — prototype (openapi-python-client) → OAG SDK

| Capability | Prototype | OAG SDK | Status |
|---|---|---|---|
| Spec cleanup (`preprocess_spec.py`) | ✅ | ✅ reused unchanged | ✅ |
| Operations | 95 | 95 | ✅ |
| Model style | attrs + dict/UNSET | **Pydantic v2** | ⬆ upgrade |
| File layout | 95 per-operation files | **13 resource API classes** | ⬆ upgrade |
| Default base URL | none | baked into `Configuration` | ⬆ upgrade |
| Lenient enums | `LenientStrEnum` | `LenientStrEnum`+`LenientIntEnum` (124) | ✅ Phase 3 |
| OAuth2 client-credentials (env) | ✅ | ✅ `Client.from_env()` | ✅ Phase 4 |
| Retries + timeout | custom transport | urllib3 `Retry` (native) | ✅ Phase 5 |
| Cursor pagination | `paginate` | `client.paginate(...)` | ✅ Phase 5/6 |
| Typed errors | custom `unwrap`+hierarchy | OAG native exceptions + helpers | ✅ Phase 5 |
| Resource facade | n/a | `client.<resource>.<op>()` | ⬆ Phase 6 |
| Examples + findings | ✅ | ✅ `oag-examples/` | ✅ Phase 7 |
| Live validation | 21/31, 0 errors | **21/31, 0 errors** | ✅ Phase 8 |
| Tests | none committed | **16 offline pytest** | ⬆ Phase 9 |

**Read-surface parity is met**, with model/ergonomics upgrades (Pydantic, resource classes, facade, tests).

## Known limitations / deferred
- **Sync only** (D1: `library=urllib3`). Async (`library=asyncio`) is additive — deferred.
- **oneOf first-match** (Phase 6): no discriminator, so two genuinely-overlapping branches
  could mis-type. Current tenant unaffected (policies are all rules). Discriminator-based
  deserialization is future polish.
- **Model-fidelity warnings** (Phase 2): generator logs `Required var urls/primaryUrl/mode
  not in properties` on application-polymorphism schemas. No runtime impact on the read
  sweep; a write-path/field-completeness audit is out of scope (write path not validated).
- **`Model.to_json()`** chokes on datetime fields — use `model_dump_json()`.

## Build & use (local, no Docker)
```
make build     # preprocess -> generate -> patch -> overlay -> smoke
make test      # offline pytest
./oag-examples/run.sh oag-examples/validate_live.py   # live (needs .env)
```
```python
from prisma_browser.extras import Client
with Client.from_env() as client:
    for user in client.paginate(client.users.list_users, limit=100):
        ...
```

## Cutover checklist (requires sign-off — NOT yet done)
The branch currently carries **both** SDKs side by side. To cut over:
1. Remove prototype artifacts: `prisma-browser-sdk/`, `overlay/`, `apply_overlay.py`,
   `opc-config.yaml`, `examples/`, `build.sh`, `tools_smoke.py`'s opc references.
2. Rename `oag-sdk/` → canonical project dir; `oag-examples/` → `examples/`.
3. Decide whether to commit generated `oag-sdk/` or gitignore it (build reproduces it).
4. Add CI: `make build && make test`.
5. Merge `migrate/openapi-generator-python` → main / make default.

**Decision required:** proceed with cutover (destructive to the prototype) or keep both
during a soak period.
