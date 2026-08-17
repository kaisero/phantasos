# Generated-CLI auth token cache — design spec

- **Date:** 2026-07-05
- **Issue:** #47 ([CLI] Auth Caching)
- **Status:** Design spec (grilled). No code yet. Precedes the implementation plan.
- **Branch (recommended):** `feature/cli-auth-token-cache` off `develop` → PR into `develop`, squash, `## [Unreleased]`.
- **Scope:** the **CLI generator** (`src/phantasos/generator/cli/`). No SDK-generator change (decision D2).

---

## 1. Problem

Every authenticated command re-runs the OAuth2 **client-credentials** grant against Strata Cloud Manager, even across back-to-back invocations, because the access token lives only in the SDK's in-process `TokenManager` and dies with the process. Issue #47 asks for a config knob to cache a JWT under `~/.<dist>/cache/` and reuse a valid token across runs.

## 2. Reality check that shaped the design

The auth flow (`generator/sdk/components/auth/scm_oauth.py.jinja`) is OAuth2 **client-credentials**: the token response carries only `access_token` + `expires_in`; the `TokenManager` stores **no refresh token** (client-credentials grants don't issue one, RFC 6749 §4.4.3). So the requirement's "refresh, or create a new auth if it can't be refreshed" collapses to a single operation: **reuse while valid, otherwise re-run the grant** (the CLI always holds client_id/secret, so it can always mint a fresh token). There is no interactive re-auth state. The one genuine robustness case is a cached token that is *unexpired but server-rejected* (revoked / mismatched) → a 401 on the API call.

`TokenManager` is essentially an **in-memory token cache** already; this feature **persists that cache across process runs**.

## 3. Decisions (from the grilling session)

| # | Decision | Rationale |
|---|----------|-----------|
| **D1** | **Refresh model = expiry + 401-retry-once.** Reuse cached token while unexpired; expired/absent → grant → cache; a **401 on the API call with a cached token** → discard cache, re-grant once, retry the call once, re-cache; a 401 after a fresh grant → real auth error (surfaced as today). | Client-credentials has no refresh token; 401-retry transparently heals revoked/stale tokens. |
| **D2** | **CLI-only; reach into `TokenManager` internals.** No SDK change. A defensive helper resolves the `TokenManager` from the built facade `Client` (single-spec: `client.api_client.configuration._token_manager`; federated: `client._configuration._token_manager`) and reads/seeds `_token` / `_expires_at`. **Fails open**: unrecognized shape → no caching, auth still works. | User choice; honors the sdk↔cli separation-of-duty. Fragility is contained by fail-open + a real-SDK test (D7). |
| **D3** | **Per-principal cache file.** `~/.<dist>/cache/token-<h>.json` where `h = sha256(f"{token_url}\n{client_id}\n{scope}")[:12]`, contents `{"access_token": …, "expires_at": …}`. File `0600`, dir `0700`. Secret is never written or keyed on; host/region excluded (don't affect token identity). | Switching credentials/scope/endpoint yields a different key → **no cross-tenant token reuse by construction**. |
| **D4** | **Config: `cache: { enabled: true, dir: null }`** + env `{PREFIX}_CACHE_ENABLED` (bool) + `{PREFIX}_CACHE_DIR` (str). `dir: null` → `~/.<dist>/cache/`. No per-command flag. | Mirrors `history`/`logging` config; `dir` override for relocation. Enabled by default per #47. |
| **D5** | **Logging** via a dedicated logger `{{package}}.auth_cache` into the existing rotating-JSONL sink. **Token value never logged** (only the key id + expiry). Lifecycle (reuse / request-new / cached-new / 401-discard) at **INFO** (default level is already `info`); degradations (unwritable dir, corrupt file) at **WARNING**; "disabled via config" at **DEBUG**. | #47 asks for INFO process logging; logging is already emitted by generated CLIs. |
| **D6** | **Management commands:** `<dist> config cache-clear` (delete all cached token files) and `<dist> show cli cache` (dir + each cached key id + expiry, never the token). | Security-hygiene purge + inspection; wired into the existing lazy-loaded meta apps. |
| **D7** | **Testing:** (a) direct offline **unit** tests of the cache module (SUT, no mocks); (b) one **ring-3** test against the REAL prisma-browser `TokenManager` with only the external token endpoint stubbed — run twice → endpoint hit once, expired→regrant, 401→invalidate+retry (verifies the private-field coupling matches the real shape); (c) a **live-gate** test hitting the real SCM token endpoint (skips without creds). | Matches the repo's real-deps / no-mock-the-SUT policy; the token server is *not* the prisma-browser API boundary, so stubbing it is allowed. |
| **D8** | **Gating:** emit the cache section, module, runtime wiring, and commands **only when the CLI has `credential_fields`** (all current products: prisma-browser, prisma-access, adem, posture). Non-authed CLIs get nothing. Enabled-by-default writes a `0600` JWT file on the first authenticated run. Unknown (non-scm) auth shape → fail open. | The feature only applies to authenticating CLIs and couples to the scm_oauth token shape. |

## 4. Architecture

### 4.1 Control flow (authenticated command)

Woven into `runtime.py` `_client()` (seed) and `run()` (persist + 401-retry). Dry-run and non-authenticating paths never touch the cache (they build a credential-free client).

```
_client():
  build facade client via _facade_from_env(**overrides)   # unchanged
  if cache enabled and credential_fields present:
     tm = _auth_cache.token_manager(client)                # defensive; None -> skip
     if tm is not None:
        key = _auth_cache.key(token_url, client_id, scope)
        hit = _auth_cache.load(key)                         # {token, expires_at} | None
        if hit and time.time() < hit.expires_at:
           tm._token, tm._expires_at = hit.token, hit.expires_at   # seed (reuse)
           log INFO "reusing cached token (key …, expires in …s)"
        # else: leave tm to fetch lazily on first request
  return client

run():  # around the API method call
  try:
     result = method(**kwargs)
  except <auth 401 with a cached token in play>:
     _auth_cache.invalidate(tm, key)         # tm._token=None; delete file
     log INFO "server rejected cached token; discarding and re-authenticating"
     result = method(**kwargs)               # tm re-grants lazily; retry ONCE
  finally / on success:
     _auth_cache.persist(tm, key)            # write tm._token/_expires_at if changed
        # logs INFO "cached new token (…)" on a fresh grant
```

`persist` writes only when the TokenManager actually holds a token (a fetch happened) and it differs from what's on disk. Atomic write: temp file in the cache dir → `os.replace` → `chmod 0600`. `load` tolerates a missing/corrupt/partial file (→ `None`, WARNING) so a bad cache never breaks a command.

**401 detection:** status **401 only** (403 = authorization, not authentication — do *not* invalidate). The SDK raises `OpenApiException` subclasses carrying `.status`; the retry branch keys on `getattr(exc, "status", None) == 401` **and** a cached token having been seeded this run.

### 4.2 New emitted module: `auth_cache.py.jinja`

Pure, unit-testable. Public surface consumed by `runtime.py`:

- `enabled() -> bool` — `_config.get().cache.enabled`.
- `cache_dir() -> Path` — `dir` override or `~/.<dist>/cache/`; `mkdir(0700)` on first write (WARNING + return sentinel on failure → caller skips).
- `key(token_url, client_id, scope) -> str` — `sha256("\n".join(...))[:12]`.
- `token_manager(client) -> Any | None` — defensive resolver for single-spec/federated shapes; `None` on anything unexpected.
- `load(key) -> _Entry | None` — read + JSON-parse + shape-check; corrupt → `None` + WARNING.
- `persist(tm, key) -> None` — atomic `0600` write of `{access_token, expires_at}` from `tm._token`/`tm._expires_at`; INFO on new token.
- `invalidate(tm, key) -> None` — `tm._token = None`; unlink the file.
- `list_entries() -> list[(key, expires_at)]` and `clear() -> int` — for the D6 commands.

Logger: `logging.getLogger(f"{_PACKAGE}.auth_cache")` (propagates to the `{{package}}` sink). Never logs the token; log lines carry `key` + human expiry.

## 5. Config recipe (per CLAUDE.md "Adding a CLI configuration option")

1. **Model** — `config.py.jinja`: new frozen `CacheConfig(enabled: bool = True, dir: str | None = None)`, wired into `CliConfiguration` via `Field(default_factory=CacheConfig)`.
2. **Default + docs** — `default_config.yml.jinja`: commented `cache:` block mirroring the model defaults (defaults-sync test enforces parity), plus the two env-var doc lines.
3. **Env** — `_ENV_MAP`: `{PREFIX}_CACHE_ENABLED → (configuration, cache, enabled)`, `{PREFIX}_CACHE_DIR → (configuration, cache, dir)`; `enabled` also joins `_BOOL_PATHS`.
4. **`effective_dict()`** — extend so `config show` includes the `cache` section.
5. **Tests** — behavioral, through the emitted package (§7).
6. **Consumers** — read via `_config.get().cache.<key>` only.

Gate every emission behind the same `{% if ir.credential_fields %}` guard the runtime already uses.

## 6. Commands (D6), wired into the lazy meta apps

- `config cache-clear` (in `config_commands.py.jinja`): `n = _auth_cache.clear(); print(f"removed {n} cached token(s) from {dir}")`.
- `show cli cache` (alongside `show cli history`): print dir + one line per `list_entries()` (`key <h>  expires <iso> (in <n>s)`), never the token.
- Register both in the lazy-loading `_META` registry (`app.py.jinja`) so `--help`/completion resolve them without eager import.

## 7. Testing (D7)

- **Unit (`tests/test_cli_emitted_cache.py`, offline):** key determinism + isolation across (token_url, client_id, scope); atomic write + `0600`/`0700`; expiry reuse vs skip; corrupt/partial file → `None` + WARNING + refetch path; unwritable dir → fail-open; `clear`/`list_entries`; `token_manager()` returns `None` for a shapeless client (fakesdk) so existing fixtures are unaffected.
- **Ring-3 (`real_sdk`, real TokenManager, stub token endpoint):** point `DEFAULT_TOKEN_URL` at a local `http.server` issuing a short-lived fake JWT (or inject a fake `_http`). Assert: run 1 grants + writes; run 2 reuses (0 grants); expired → regrant; injected 401 → invalidate + retry + re-cache. This is the backstop that `_token`/`_expires_at`/resolver match the real shapes.
- **Live (skips without creds):** real SCM grant, 2nd run reuses, real 401 handling.

## 8. Security posture

- JWT at rest in a `0600` file under a `0700` dir (mirrors logging/history). Enabled by default (per #47) → first authenticated run writes a token file; opt out with `{PREFIX}_CACHE_ENABLED=false`. Purge with `config cache-clear` or `rm -rf ~/.<dist>/cache/`.
- Client secret is **never** persisted or used as key material. Token value is **never** logged. History already omits auth headers; unchanged.
- Per-principal keying prevents a token minted for one principal from being used by another.

## 9. Edge cases / fail-open matrix

| Condition | Behavior |
|-----------|----------|
| Cache disabled (config/env) | No file I/O; DEBUG "disabled"; normal per-run grant. |
| Cache dir unwritable | WARNING; command proceeds without caching. |
| Corrupt / partial / wrong-shape file | Ignored (treated as miss); WARNING; regrant. |
| Unrecognized auth/client shape (`token_manager()` → None) | No caching; auth via normal path. |
| dry-run / non-auth command | Cache untouched (credential-free client). |
| Concurrent invocations | Last-writer-wins via atomic replace; tokens are interchangeable, no lock needed. |
| 403 (authorization) | Not an auth failure — not retried, cache untouched. |

## 10. Out of scope

- Any SDK-generator change (token-store hook, `token_url`/static-token entry point). D2 keeps it CLI-only.
- Refresh-token / interactive-auth flows (don't exist in client-credentials).
- Encrypting the at-rest token or OS keyring integration (0600 file matches existing history/logging posture; revisit if requested).
- A per-command `--no-cache` flag (env var covers one-off disable).
- Caching for non-scm auth components (fail-open until a component is explicitly supported).

## 11. Open questions

None blocking. Confirm at plan time: exact `config cache-clear` placement (top-level `config` group vs a `cache` sub-group) and whether `show cli cache` should also report the *active* run's key for quick correlation.
