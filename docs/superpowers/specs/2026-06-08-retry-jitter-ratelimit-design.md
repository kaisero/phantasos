# Design: Modern retry (jitter) + typed RateLimitException

**Date:** 2026-06-08
**Status:** Draft for review (revised after senior architecture review)
**Branch:** `sdk-retry-jitter` (off `main`)
**Closes:** Gap report §4.2 (Retries — no jitter / no defaults) and §4.3 (Rate limiting — no typed 429 exception). Report: `docs/research/2026-06-08-sdk-feature-gap-analysis.md`.

## Goal

Give every generated SDK a **modern retry policy with jitter** (on by default) and replace the
`is_rate_limited()` helper with a first-class, user-friendly **`RateLimitException`**. This change
also **establishes the layered architecture** phantasos will use for the rest of the modern-SDK
roadmap.

## Architecture: a deliberate three-tier model

A senior review concluded that a strict "never modify generated code" rule cannot deliver the full
roadmap (async, raw/streaming, request hooks, a rich typed-error hierarchy) — those must live on the
core client/every entry point, which `extras/` cannot reach cleanly; forcing them through `extras/`
yields fragile runtime proxies that couple to OAG internals *invisibly*. So phantasos adopts three
tiers, **preferring the least-invasive tier that delivers the capability on all entry points**:

- **Tier 1 — `extras/` augmentation (preferred).** Additive composition over public seams / the
  facade: auth, pagination helpers, error helpers, facade, branded User-Agent, **`JitteredRetry`
  wiring**, idempotency headers, webhooks, OTel. No generated-code changes.
- **Tier 2 — OAG custom templates (`-t <dir>`, override only the few `.mustache` files we touch).**
  For capabilities that must live in the *core generated client and be present on every path*: the
  typed-error hierarchy (incl. **429 → `RateLimitException` dispatch**), request/response hooks,
  raw/streaming responses, per-method options. OAG falls back to its built-in templates for every
  file we don't override, so coupling is bounded to the few files we own.
- **Tier 3 — `patches.py` source surgery.** Reserved for bug-fixes to OAG output (where it already
  lives: apostrophe/lenient enums, oneOf) and as a small escape hatch — not for net-new features.

**Async is a special case → generate twice.** True async needs generated `async def` bodies; an
external wrapper can only fake it with a thread pool. OAG's python generator already offers
`library=asyncio`/`httpx`. The future async story is a second generation (e.g. `<pkg>/aio/`) sharing
`models/`, exposing `AsyncClient` — *not* an external wrapper. (Out of scope here; recorded as the
intended path so this spec doesn't preclude it.)

The only generated runtime seam this feature relies on for retry is `configuration.retries` —
urllib3's own documented extension point that `rest.py` already reads.

## Scope (this change)

**In:**
1. **`JitteredRetry`** (urllib3.Retry subclass) + on-by-default wiring — **Tier 1**.
2. **Typed `RateLimitException`** with 429 dispatch in generated `exceptions.py` via an OAG
   **`exceptions.mustache` override** — **Tier 2** (covers facade *and* raw `ApiClient` users; seeds
   the broader error-hierarchy gap).
3. Removal of `is_rate_limited()`.
4. **New phantasos capability: OAG custom-template overrides** — ship a templates dir and pass
   `-t <dir>` to OAG (the Tier-2 mechanism), with `exceptions.mustache` as its first user.

**Out (future gap items):** per-request `with_options()`, idempotency keys, retry-count header,
proactive throttling / `X-RateLimit-*` sleeping, async (generate-twice), `x-should-retry`, the
*rest* of the typed-error hierarchy (network/timeout/5xx-granularity, `.response`/`.request`) — the
`exceptions.mustache` override here is the foundation those build on, but we add only 429 now.

## Tier 1 — the `retry` component

A dedicated, typed component, **on by default** (every SDK gets it unless `retry: false`).

### `sdk.yml` config (typed `RetryConfig`, pydantic `extra="forbid"`)

```yaml
retry:                         # optional; on-by-default. `retry: false` disables.
  max_retries: 3
  backoff_base: 0.5            # seconds
  backoff_max: 8.0             # seconds (cap)
  jitter_frac: 0.25            # multiplicative jitter fraction
  statuses: [408, 429, 500, 502, 503, 504]
  respect_retry_after: true
```

All fields default as shown (zero config needed). `retry: false` disables. Modelled like `facade`
(`bool | dict`).

### Vendored template → `extras/retry.py` (`components/retry/jittered_retry.py.jinja`)

- **`JitteredRetry(urllib3.Retry)`** — overrides `get_backoff_time()` (urllib3's documented hook):
  ```
  exp = min(backoff_base * 2 ** (consecutive_errors - 1), backoff_max)
  return exp * (1 - jitter_frac * random())     # cloudflare-style multiplicative jitter
  ```
  `Retry-After` handling stays urllib3's; jitter only affects the exponential path. Stateless.
- **`default_retry() -> JitteredRetry`** — `total=max_retries`, `status_forcelist=statuses`,
  `allowed_methods=None`, `respect_retry_after_header=respect_retry_after`, `raise_on_status=False`.

Consumed by `facade` (every client it builds sets `cfg.retries = default_retry()` when retry is
enabled and no explicit `retries` given) and by `auth` (replaces its private `_retry()` with the
shared `default_retry()`).

## Tier 2 — `RateLimitException` via an OAG template override

phantasos ships an OAG template directory (e.g. `src/phantasos/oag_templates/python/`) containing a
single overridden file, **`exceptions.mustache`** — a copy of OAG 7.22.0's python `exceptions.mustache`
with two additions:

1. A **`RateLimitException(ApiException)`** class with:
   - `retry_after: float | None` — parsed from the response `Retry-After` header in both standard
     forms (integer seconds, and HTTP-date via `email.utils.parsedate_to_datetime`).
   - `reset: float | None` — convenience from `X-RateLimit-Reset` (epoch → seconds-from-now) when
     present.
   - inherited `.status` (429), `.headers`, `.body`, `.reason`.
2. A branch in **`ApiException.from_response()`**: `if http_resp.status == 429: raise RateLimitException(...)`.

`generate.py` passes `-t <abs path to phantasos oag_templates>` to OAG. OAG uses our
`exceptions.mustache` and its own built-in templates for everything else. The base template must be
extracted from the pinned OAG jar (`openapi-generator author template -g python`) and minimally
edited — the plan verifies the rendered `exceptions.py` is valid and the diff vs. upstream is small.

Because dispatch is in generated `from_response()`, **every** path raises `RateLimitException`
(facade and bare `ApiClient(Configuration())`). **No facade proxy** is needed (the previously-specced
`_RateLimitAware` shim is dropped).

## `errors` component changes (Tier 1)

- **Re-export `RateLimitException`** from `..exceptions` (now generated) in `extras/errors.py`'s
  `__all__`, alongside the other typed exceptions.
- **Remove `is_rate_limited()`**; keep `error_message()`.

## `facade` / `auth` component changes (Tier 1)

- **`facade`:** wire `default_retry()` into the `Configuration` of every `Client` it builds. **No**
  429 proxy (handled by the template). Annotations/typing unchanged.
- **`auth`:** `api_client_from_env`/`api_client_from_credentials` set `cfg.retries = default_retry()`
  (replacing the private `_retry()`), so one retry definition is shared.

## Wiring / context

- `productconfig`: `retry: RetryConfig | bool = True` on `ProductConfig`; resolved like `facade`
  (default-on); registry entry for the `retry` component; `render.vendor` writes `extras/retry.py`
  and exposes `has_retry` + retry fields in the context so `facade`/`auth` import from `extras.retry`.
- `extras/__init__.py` re-exports `JitteredRetry`, `default_retry`, `RateLimitException`.

## Scaffold test changes (built-in component tests)

- **Update `scaffold/tests/test_errors.py.jinja`:** assert `RateLimitException` is importable, is an
  `ApiException` subclass, has a `retry_after` attribute; **drop** the `is_rate_limited` assertion.
- **Add `scaffold/tests/test_retry.py.jinja`** (gated on `has_retry`): assert `JitteredRetry` import;
  `get_backoff_time()` ∈ `[0.75*exp, exp]` and ≤ `backoff_max`; `default_retry()` has configured
  `total`/`status_forcelist`.

## Migration & verification

Both example products (`prisma-browser`, `adem`) get retry + `RateLimitException` with **zero
config** (default-on; both have `facade` + `auth`). Rebuild → each SDK has `extras/retry.py`, a
generated `RateLimitException` (429-dispatched), retry wired through facade + auth; the regenerated
component test suite (now testing `RateLimitException` + retry) passes; smoke is green.

## Backward-incompatible note

`is_rate_limited()` is removed — callers migrate to `except RateLimitException`. Acceptable: SDKs are
regenerated artifacts and this is the requested ergonomic improvement.

## Unchanged

- No change to generated `rest.py`/`api_client.py`/`configuration.py`/`api/*` (only `exceptions.py`
  is template-overridden, declaratively, via OAG's own mechanism).
