# components

Validated against 81e8207 on 2026-06-20 · Purpose: reusable, Jinja-templated SDK extras selected per-product and vendored into `<package>/extras/`.

## Purpose & responsibilities

The components subsystem provides the five families of reusable behaviour
(`auth`, `pagination`, `errors`, `facade`, `retry`) that a product's `sdk.yml`
opts into. At vendor time each selected component is rendered from a Jinja
template into `<package>/extras/<name>.py` — a self-contained Python file that
ships with the SDK and has no dependency on phantasos. The SDK consumer imports
directly from `extras/`.

## How it works

Three layers cooperate:

1. **Param model** (`src/phantasos/config.py`) — a frozen Pydantic model per
   component carrying the defaults and the `template` path. The model is
   referenced from a built-in registry (`BUILTIN_AUTH`, `BUILTIN_PAGINATION`,
   `BUILTIN_ERRORS`, `BUILTIN_FACADE`, `BUILTIN_RETRY`).
2. **sdk.yml declaration** (`products/<name>/sdk.yml`) — a `type:` key selects
   the registry entry; additional keys override model defaults. A relative
   `.jinja` path in `type:` bypasses the registry and loads a
   product-local template as a `CustomComponent`.
3. **Render/vendor** (`src/phantasos/generator/sdk/render.py::vendor()`) —
   `vendor()` receives a `LoadedProduct` (resolved by `productconfig.load_product`
   into concrete component models). For each present component it calls
   `write_component()`: dumps the model's fields, pops `template`, and renders
   the Jinja template with the full context dict merged with those fields. The
   rendered source is written to `extras/<name>.py`. The `__init__.py`
   re-exports every selected family via conditional `{% if has_<family> %}` blocks
   in `extras_init.py.jinja`.

Cross-component wiring: `has_auth`, `has_pagination`, `has_retry`, `has_facade`,
`has_errors` are boolean context keys available to every template. `auth` and
`facade` templates both import `from .retry import default_retry` when
`has_retry` is true; `facade` imports from `auth` and `pagination` the same way.
`retry` is always vendored when any component that uses it is present (facade
declares `retry: true` by default in sdk.yml).

`include:` in sdk.yml copies additional product-local templates into `extras/`
without mapping through a registry; path-escape out of `extras/` raises
`ValueError`.

## The five families {#families}

### auth

- **Registry key:** `scm_oauth`
- **Base class:** `AuthComponent` — the common base for every auth strategy. It
  declares `credential_fields()`, which subclasses MUST override (enforced at
  class-definition time via `__init_subclass__`). Each returned `CredentialField`
  describes one credential the component exposes (`name`, `env_var`, `secret`,
  `required`, optional `client_kwarg`); `CredentialField` lives in
  `generator/cli/ir.py` so it travels into the emitted CLI's `spec.py`. The CLI
  generator reads these descriptors to drive named environments, credential
  prompting, and the missing-credential pre-flight (see `cli-generator.md`).
- **Param model:** `ScmOAuth` ("Strata Cloud (SCM/SASE) OAuth2
  client-credentials provider") — `token_url`, `scope_env` (`SCOPE`),
  `client_id_env` (`CLIENT_ID`), `client_secret_env` (`CLIENT_SECRET`),
  `base_url_env` (`BASE_URL`), `config_class_name` (default `SdkConfiguration`).
  Its `credential_fields()` exposes `client_id`, `client_secret` (secret),
  `scope`, and an OPTIONAL `base_url` (`client_kwarg="host"`; the SDK host has a
  default).
- **Template:** `auth/scm_oauth.py.jinja`
- **Renders:** `extras/auth.py` — `TokenManager` (auto-refreshing
  client-credentials grant via Basic auth over urllib3), a `Configuration`
  subclass whose `access_token` property delegates to `TokenManager`,
  `api_client_from_credentials()`, `api_client_from_env()`.
- **Named environments:** for a generated CLI, the credentials these fields name
  can also come from a named environment in `~/.{distribution}/environments.yml`
  (per-field env vars still win). The resolution + environment CLI lives in the
  CLI generator, not here — see `cli-generator.md`.

### pagination

- **Registry key:** `cursor`
- **Param model:** `CursorPagination` — `data_field` (`data`),
  `page_info_field` (`page_info`), `cursor_field` (`cursor`),
  `has_next_field` (`has_next_page`).
- **Template:** `pagination/cursor.py.jinja`
- **Renders:** `extras/pagination.py` — `paginate(list_method, **kwargs)`
  iterator that walks pages via cursor until `has_next_field` is false.

### errors

- **Registry key:** `nested`
- **Param model:** `NestedError` — `error_field` (`error`),
  `message_field` (`message`), `code_field` (`code`).
- **Template:** `errors/nested_error.py.jinja`
- **Renders:** `extras/errors.py` — re-exports the OAG-generated exception
  classes and adds `error_message(exc)` that extracts a human-readable string
  from `body[error_field][message_field]`.

### facade

- **Registry key:** `default`
- **Param model:** `Facade` — no user-settable params beyond `type`.
- **Templates:** `facade/client.py.jinja` (the `Client` facade) and
  `facade/resource.py.jinja` (the per-object typed wrappers).
- **Renders:** `extras/facade.py` + `extras/resources.py` — emitted in **two
  passes** (see `sdk-generator.md` Render step for the full flow):
  - **Pass 1:** a raw-only `extras/facade.py` exposing only `_RESOURCES` (the
    `{api_attr: *Api class}` map) so the package is importable for the wrapper
    build step.
  - **`extras/resources.py`:** the object-granular typed resource wrappers
    (`<Object>Resource` classes). Each class carries `_bindings: ClassVar[dict]`
    (verb → list of raw-op dicts) and typed clean methods (`get`/`list`/`create`/
    `update`/`delete`/non-CRUD) that delegate to generic `_select`/`_to_raw`/
    `_call`/`_fetch`/`_list` helpers. `list(all_pages=True)` paginates internally
    via the vendored `paginate(...)` and returns `page.model_copy(update={"data":
    items})`. `_serialize(verb, **kwargs)` is the dry-run twin (no HTTP send).
  - **Pass 2:** a full `extras/facade.py` adding `_WRAPPERS` (the
    `{object_attr: (WrapperClass, api_attr)}` map) and wiring each `client.<object>`
    to a wrapper instance that SHARES a single `*Api` instance per backing api
    class. Raw `*Api` instances are not reachable from the public `client.<object>`
    surface. Exposes `from_env()` / `from_credentials()` classmethods when
    `has_auth`; wires `default_retry()` when `has_retry`; still exposes
    `api_client` for HTTP capture. The old `paginate()` method is retained when
    `has_pagination` for backward compatibility, but the wrapper's `all_pages=True`
    is the preferred path.

### retry

- **Registry key:** `default`
- **Param model:** `RetryConfig` — `max_retries` (3), `backoff_base` (0.5),
  `backoff_max` (8.0), `jitter_frac` (0.25), `statuses`
  (`[408,429,500,502,503,504]`), `respect_retry_after` (`True`).
- **Template:** `retry/jittered_retry.py.jinja`
- **Renders:** `extras/retry.py` — `JitteredRetry` (urllib3 `Retry` subclass
  with multiplicative jitter in `get_backoff_time()`) and `default_retry()`
  factory. Vendored unconditionally when `facade: true` or any component that
  references retry is selected.

## Build / run pointers

- **Template directory:** `src/phantasos/generator/sdk/components/` — one
  `<family>/<strategy>.py.jinja` per built-in strategy plus
  `extras_init.py.jinja` at the root.
- **Param models and registries:** `src/phantasos/config.py`.
- **Vendor logic:** `src/phantasos/generator/sdk/render.py::vendor()`.
- **Unit tests:** `tests/test_render.py` — covers full vendoring, facade-only,
  `include:`, custom template, retry wiring, path-escape rejection.
- **Adding a component:**
  1. Add a Jinja template under `components/<family>/`.
  2. Add a param model in `config.py` and register it in `BUILTIN_<FAMILY>`.
  3. Add a `write_component()` call for the new family in `render.py::vendor()`.
  4. Add `{% if has_<family> %}` imports to `extras_init.py.jinja`.
  5. Test with `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s gate`.

## Public API

<!-- GENERATED:api -->
- `config.py`
  - class `AuthComponent` — Base class for all auth components.
  - class `ScmOAuth` — Strata Cloud (SCM/SASE) OAuth2 client-credentials provider.
  - class `CursorPagination` — Cursor pagination: items under `data_field`, cursor under page_info.
  - class `NestedError` — Error message at ``body[error_field][message_field]`` (+ optional code).
  - class `Facade` — Resource facade: binds generated *Api classes as client.<resource>.
  - class `RetryConfig` — Retry policy with jitter (urllib3.Retry subclass) — on by default.
  - class `OperationOverride` — Declarative rename of a single SDK operation (keyed by ``resource.method``).
<!-- /GENERATED:api -->

## Gotchas / invariants

- **No `.py` files live under `components/`** — the directory contains only
  `.jinja` templates. The param models are in `src/phantasos/config.py`, which
  the Public API block below targets (`components/**/*.py` yields zero files;
  `render.py`'s vendor step is documented in `sdk-generator.md`).
- **`retry` is unconditional when `facade: true`** — `ProductConfig` defaults
  `retry: true`, so unless the product explicitly sets `retry: false`, retry is
  always vendored. `facade` and `auth` templates both reference
  `default_retry()`, so the templates guard the import on `has_retry`.
- **Custom components bypass the registry** — if `type:` starts with `./` or
  ends with `.jinja`, `resolve_component()` treats it as a path-relative
  template and validates it via `CustomComponent` (`extra="allow"`), allowing
  arbitrary extra keys to flow through as template context.
- **Context keys are reserved** — `vars:` in sdk.yml may not shadow the
  auto-exposed names (package, base_url, has_auth, etc.); `load_product()`
  raises `ValueError` on collision.
- **Facade resource discovery is build-time, not runtime** — `_discover_resources()`
  parses `api/__init__.py` with a regex; it must run after OAG generates that
  file. Attribute names drop the trailing `_api` suffix (e.g. `things_api` →
  `things`).
- **`include:` path-escape is enforced** — destination paths that resolve
  outside `extras/` raise `ValueError`; source paths that escape the product
  directory also raise at load time.

## See also

- `sdk-generator.md` — full build pipeline; the "Render/vendor" stage calls
  `vendor()` described here.
- `product-config.md` — `LoadedProduct`, `ProductConfig`, `resolve_component()`.
- `src/phantasos/config.py` — param models and registry dicts.
- `src/phantasos/generator/sdk/render.py` — `vendor()` implementation.
- `tests/test_render.py` — unit tests for the vendor step.
