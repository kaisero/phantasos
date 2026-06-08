# Design: Modern retry (jitter) + typed RateLimitException

**Date:** 2026-06-08
**Status:** Draft for review
**Branch:** `sdk-retry-jitter` (off `main`)
**Closes:** Gap report §4.2 (Retries — no jitter / no defaults) and §4.3 (Rate limiting — no typed 429 exception). Report: `docs/research/2026-06-08-sdk-feature-gap-analysis.md`.

## Goal

Give every generated SDK a **modern retry policy with jitter** (on by default) and replace the
`is_rate_limited()` helper with a first-class, user-friendly **`RateLimitException`** — all via a
clean **augmentation layer** that wraps the generated primitives. **Generated code is never
modified** (no `patches.py` surgery, no OAG template forks).

## Architectural principle: the augmentation layer

phantasos enhances the generated SDK by **subclassing/composing** over its primitives, exposed
through the supported entry point (the `facade` `Client`). The generated classes stay pristine
("raw primitives"); phantasos's `extras/` classes are the supported surface. This is the reusable
pattern for *future* capabilities too (hooks, telemetry, User-Agent, etc.) — each is an override
on a phantasos subclass or a small `extras/` module, wired through the facade. The retry default
applies through this entry point; a caller reaching past it to the bare generated `Configuration`
opts out (using internals).

The only generated seam we rely on is `configuration.retries` — **urllib3's own documented
extension point** that `rest.py` already reads.

## Scope

**In:** `JitteredRetry` (urllib3.Retry subclass) + on-by-default wiring; typed `RateLimitException`
surfaced at the facade; removal of `is_rate_limited()`.

**Out (future gap items, per the report):** per-request `with_options(max_retries=…)` overrides,
idempotency keys, `x-stainless-retry-count` request header, proactive throttling / `X-RateLimit-*`
-driven sleeping, async retry, the `x-should-retry` server hint.

## New `retry` component

A dedicated, typed component — **on by default** (every SDK gets it unless `retry: false`).

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

All fields default as shown, so a product needs **zero** config. `retry: false` skips the
component and the wiring. Modelled like `facade` (`bool | dict`).

### Vendored template → `extras/retry.py`

`components/retry/jittered_retry.py.jinja` renders:

- **`JitteredRetry(urllib3.Retry)`** — overrides `get_backoff_time()` (urllib3's documented hook):
  ```
  exp = min(backoff_base * 2 ** (consecutive_errors - 1), backoff_max)
  return exp * (1 - jitter_frac * random())     # cloudflare-style multiplicative jitter
  ```
  `Retry-After` handling stays urllib3's (`respect_retry_after_header=…`), so jitter only affects
  the exponential path. Stateless (clean fit for a `Retry` subclass).
- **`default_retry() -> JitteredRetry`** — factory returning a `JitteredRetry` configured from the
  block: `total=max_retries`, `status_forcelist=statuses`, `allowed_methods=None` (retry all verbs),
  `respect_retry_after_header=respect_retry_after`, `raise_on_status=False`.

## `errors` component changes

- **Add `RateLimitException(ApiException)`** with:
  - `retry_after: float | None` — parsed from the response `Retry-After` header in **both** standard
    forms: integer seconds, and HTTP-date (`email.utils.parsedate_to_datetime`).
  - `reset: float | None` — convenience parsed from `X-RateLimit-Reset` (epoch → seconds-from-now)
    when present.
  - inherited `.status` (429), `.headers`, `.body`, `.reason`; `error_message(exc)` still works.
  - `classmethod from_api_exception(exc) -> RateLimitException` — builds it from a caught 429
    `ApiException`, copying status/reason/body/headers and parsing `retry_after`/`reset`.
- **Remove `is_rate_limited()`**; update `__all__` (drop `is_rate_limited`, add `RateLimitException`).
  `error_message()` stays.

## `facade` component changes

- **Wire retry by default:** the `Client` it builds applies `default_retry()` to its
  `Configuration` (when retry is enabled and the config has no explicit `retries`), so every facade
  client retries — independent of auth.
- **Surface `RateLimitException`:** each bound resource is wrapped in a thin proxy that forwards
  attribute access to the generated `*Api` instance and, on a caught `ApiException` with
  `status == 429`, raises `RateLimitException.from_api_exception(exc)`. The proxy preserves the
  resource type annotations (`{{ r.attr }}: {{ r.cls }}`), so static typing/IDE autocomplete are
  unaffected; only runtime behavior is augmented. Non-429 `ApiException`s propagate unchanged.

```python
class _RateLimitAware:
    def __init__(self, api): self._api = api
    def __getattr__(self, name):
        attr = getattr(self._api, name)
        if not callable(attr):
            return attr
        @functools.wraps(attr)
        def call(*a, **k):
            try:
                return attr(*a, **k)
            except ApiException as exc:
                if getattr(exc, "status", None) == 429:
                    raise RateLimitException.from_api_exception(exc) from exc
                raise
        return call
```

## `auth` component changes

- Replace its private `_retry()` with the `retry` component's `default_retry()` (single retry
  definition consumed across the layer). `api_client_from_env`/`api_client_from_credentials` set
  `cfg.retries = default_retry()` (unless retry disabled).

## Wiring / context

- `productconfig`: `retry: RetryConfig | bool = True` on `ProductConfig`; resolved like `facade`
  (default-on). A new built-in component registry entry; `render.vendor` writes `extras/retry.py`
  when enabled and exposes `has_retry` + the retry fields in the template context so `facade`/`auth`
  import from `extras.retry`.
- `extras/__init__.py` (`extras_init.py.jinja`) re-exports `JitteredRetry`, `default_retry`,
  `RateLimitException` for ergonomic imports.

## Scaffold test changes (built-in component tests)

- **Update `scaffold/tests/test_errors.py.jinja`:** assert `RateLimitException` is importable, is an
  `ApiException` subclass, and has a `retry_after` attribute; **drop** the `is_rate_limited`
  assertion.
- **Add `scaffold/tests/test_retry.py.jinja`** (gated on `has_retry`): assert `JitteredRetry` import;
  that `get_backoff_time()` returns a value within `[0.75*exp, exp]` and never exceeds
  `backoff_max`; that `default_retry()` has the configured `total`/`status_forcelist`.

## Migration

Both example products (`prisma-browser`, `adem`) get retry **with zero config** (default-on; both
have `facade` + `auth`). Rebuild → each SDK gains `extras/retry.py`, `RateLimitException`, retry
wired through facade + auth, and the regenerated component test suite (now testing
`RateLimitException` + retry) passes.

## Backward-incompatible note

`is_rate_limited()` is removed from generated SDKs — callers migrate to `except RateLimitException`.
Acceptable: SDKs are regenerated artifacts, and this is the requested ergonomic improvement.

## Out of scope / unchanged

- Async (gap §4.1), per-request overrides, idempotency, proactive throttle — future gaps.
- No change to generated `rest.py`/`api_client.py`/`exceptions.py`/`configuration.py` source.
