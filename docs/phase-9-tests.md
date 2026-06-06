# Phase 9 — Tests  ✅

## Goal
A committed, **offline** (no live calls) pytest suite covering the overlay + key SDK behavior.

## What was built (`tests/`)
- `conftest.py` — puts `oag-sdk/` on `sys.path`; silences expected lenient-enum warnings.
- `test_lenient_enums.py` — known str value canonical; unknown str (`scm`) and int (`9999`)
  pass through, are recorded, and serialize back to the real value.
- `test_auth.py` — token caching (1 fetch / 2 calls), refresh on expiry, `Configuration`
  `access_token` property → `Bearer …`, `api_client_from_env` missing-var error.
- `test_pagination.py` — `paginate` follows the cursor across pages; empty case.
- `test_errors.py` — `error_message` extracts `{error:{message}}`, falls back to reason;
  `is_rate_limited` (429).
- `test_facade.py` — `Client.from_credentials` wires all 13 resources without network.
- `test_models.py` — `User` round-trip; tolerates unknown enum value.

## Run
```
make test       # uv run pytest tests/ -q
```

## Acceptance evidence
`16 passed` (4 expected lenient-enum warnings). Fully offline — safe for CI (no `.env`,
no network).

## Note
Tests require the SDK to be generated first (`make build`), since they import
`prisma_browser` from `oag-sdk/`. In CI: `make build && make test`.
