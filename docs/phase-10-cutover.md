# Phase 10 — Docs & cutover  ✅ DONE

> **Cutover executed.** The prototype (openapi-python-client) was removed and the OAG SDK
> promoted to canonical names: `oag-sdk/`→`prisma-browser-sdk/`, `oag-overlay/`→`overlay/`,
> `oag-examples/`→`examples/`. CI added (`make build && make test`). `make build`/`make test`
> verified green on the new paths.

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
./examples/run.sh examples/validate_live.py   # live (needs .env)
```
```python
from prisma_browser.extras import Client
with Client.from_env() as client:
    for user in client.paginate(client.users.list_users, limit=100):
        ...
```

## Cutover checklist — DONE
1. ✅ Removed prototype artifacts (old `prisma-browser-sdk/` package, `overlay/`,
   `apply_overlay.py`, `opc-config.yaml`, `examples/`, `build.sh`).
2. ✅ Promoted `oag-sdk/`→`prisma-browser-sdk/`, `oag-overlay/`→`overlay/`,
   `oag-examples/`→`examples/`.
3. ✅ Generated SDK kept committed (consumers can use it without building; `make build`
   reproduces it deterministically).
4. ✅ CI added (`.github/workflows/ci.yml`: `make build && make test`).
5. ☐ Merge `migrate/openapi-generator-python` → main / make default (your call — left to you).
