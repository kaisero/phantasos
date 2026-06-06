# Prisma Browser Python SDK

A native, resource-oriented Python SDK for the Prisma Browser Management API,
generated from the OpenAPI spec (OpenAPI Generator, `python`/Pydantic v2) plus a
hand-written overlay (auth, retries, pagination, errors, resource facade).

## Quickstart
```bash
make build          # generate the SDK (needs JRE 11+ and uv; no Docker)
make test           # offline test suite
```
```python
from prisma_browser.extras import Client      # prisma-browser-sdk/ on sys.path
with Client.from_env() as client:             # CLIENT_ID / CLIENT_SECRET / SCOPE
    for user in client.paginate(client.users.list_users, limit=100):
        print(user.name, user.email)
    rule = client.security_policy.get_security_rule_by_id(rule_id)
```

## Layout
| Path | What |
|------|------|
| `prisma-browser-sdk/prisma_browser/` | generated SDK (13 resource API classes + Pydantic models) + `extras/` overlay |
| `overlay/` | hand-written overlay source (copied into `extras/` by the build) |
| `examples/` | runnable read-only examples (`./examples/run.sh`) |
| `tests/` | offline pytest suite (`make test`) |
| `preprocess_spec.py`, `apply_patches.py`, `Makefile` | the build pipeline |
| `findings/` | spec-vs-reality findings (enum gaps, etc.) |
| `docs/` | migration phase docs |

## Build pipeline (`make build`)
`preprocess` (clean spec) → `generate` (OpenAPI Generator) → `patch` (codegen fixups +
lenient enums + oneOf) → `overlay` (copy `overlay/` → `extras/`) → `smoke` (import check).
Idempotent and deterministic. The generator jar is pinned and fetched to `.tools/`.

## Auth
OAuth2 client-credentials via `CLIENT_ID`, `CLIENT_SECRET`, `SCOPE` (`tsg_id:<id>`); see
`.env.example`. Tokens auto-refresh.

See `docs/` for the full design history and known limitations.
