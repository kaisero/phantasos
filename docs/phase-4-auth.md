# Phase 4 — Auth (OAuth2 client-credentials)  ✅

## Goal
Port the prototype's env-driven OAuth2 client-credentials auth (with auto-refresh) to
the OpenAPI-Generator SDK.

## What was built
`oag-overlay/auth.py` (copied into `prisma_browser/extras/` by `make overlay`):
- **`TokenManager`** — performs the client-credentials grant via urllib3
  (`POST auth.apps.paloaltonetworks.com/oauth2/access_token`, HTTP-Basic creds,
  `grant_type=client_credentials`, `scope=tsg_id:<id>`), caches the token, refreshes
  60s before the ~15-min expiry. Thread-safe.
- **`PrismaSaseConfiguration(Configuration)`** — overrides `access_token` as a *property*
  delegating to the `TokenManager`. The generated client reads `configuration.access_token`
  per request when applying the Bearer header, so refresh is transparent.
- **`api_client_from_credentials(...)` / `api_client_from_env()`** — read
  `CLIENT_ID` / `CLIENT_SECRET` / `SCOPE` (+ optional `PRISMA_SASE_BASE_URL`), build a
  configured `ApiClient`. Host defaults to `https://api.sase.paloaltonetworks.com`.
  (Retries wired here too — finalized in Phase 5.)

## How it integrates
OAG's `Configuration.access_token` is consulted in `auth_settings()` at request time, so a
property getter that returns a fresh token is sufficient — no per-call wrapping needed.

## Acceptance evidence
- **Unit (stubbed fetch):** 1 fetch served 2 calls (cached); forcing expiry triggered a
  second fetch; `auth_settings()` produced `Bearer <token>`; host defaulted correctly.
- **Live:** `api_client_from_env()` → `UsersApi.list_users(limit=2)` → **200**, returned
  Oliver Kaiser (`provider: UserProvider.scm` — lenient enum active end-to-end).

## Files
- `oag-overlay/auth.py`, `oag-overlay/__init__.py`
- `Makefile`: `overlay` target (copies overlay → `extras/`); added to `build`.

## Follow-ups
- Retries/timeout defaults are set in `api_client_from_*` but exercised/verified in Phase 5.
- Env var names match the prototype (`SCOPE` holds the full `tsg_id:<id>`).
