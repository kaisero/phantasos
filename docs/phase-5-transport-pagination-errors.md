# Phase 5 — Transport (retries/timeout), pagination, errors  ✅

## Goal
Parity for retries/backoff, cursor pagination, and typed error handling.

## What was built / reused
- **Retries (reused OAG):** `api_client_from_*` sets `configuration.retries` to a
  `urllib3.Retry(total, status_forcelist=[429,500,502,503,504], backoff_factor=0.5,
  respect_retry_after_header=True, allowed_methods=None, raise_on_status=False)`.
  OAG's `rest.py` passes this straight to the urllib3 `PoolManager`.
- **Timeout:** per-request `_request_timeout` is supported by every generated method;
  the facade (Phase 6) sets a default. (No global-timeout field in OAG `Configuration`.)
- **Errors (reused OAG + thin helpers):** OAG already raises a typed hierarchy
  (`ApiException`, `BadRequestException` 400, `UnauthorizedException` 401,
  `ForbiddenException` 403, `NotFoundException` 404, `ServiceException` 5xx). No `unwrap`
  needed — the high-level methods raise on non-2xx automatically. Added in
  `oag-overlay/errors.py`: `is_rate_limited(exc)` (429) and `error_message(exc)` (extracts
  `{error:{message}}` from the body, falls back to the HTTP reason).
- **Pagination:** `oag-overlay/pagination.py::paginate(list_method, **filters)` drives the
  cursor loop and yields items.

## Acceptance evidence (live)
- Retries: `configuration.retries` is a `Retry` with `status_forcelist=[429,500,502,503,504]`.
- Pagination: `paginate(UsersApi(ac).list_users, limit=10)` iterated the tenant's users.
- Typed error: `get_user_by_id("000…")` → `NotFoundException` (status 404); `error_message`
  → "Not Found" (empty body → reason fallback); `is_rate_limited` → False.

## Difference from the prototype
The prototype needed a custom `unwrap()` + `ApiException` tree + `RetryTransport` because
openapi-python-client returns instead of raising and has no retries. OAG provides both
natively, so this phase is mostly **reuse + thin helpers** rather than a rebuild.

## Files
`oag-overlay/pagination.py`, `oag-overlay/errors.py`, `oag-overlay/__init__.py` (re-exports).
