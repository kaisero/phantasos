# Authoring a spec (`sdk.py`)

`sdkgen` builds a vendored, self-contained Python SDK for an OpenAPI spec from a small
Python config module. You write one `sdk.py`; `sdkgen build ./sdk.py` does the rest.

## Quickstart
```bash
pip install -e ".[generated]"      # the framework (+ deps the generated SDK imports)
sdkgen build ./sdk.py              # preprocess -> generate -> patch -> vendor -> smoke
```
Needs a JRE (11+) on `PATH`; the OpenAPI Generator jar is fetched once to `~/.cache/sdkgen`
(override with `SDKGEN_CACHE`).

## The `sdk.py` module
Define a module-level `CONFIG` and, optionally, `preprocess(spec)` / `patch(pkg_dir)` hooks.

```python
from sdkgen import SdkConfig, OAuthClientCredentials, CursorPagination, NestedError, Facade

CONFIG = SdkConfig(
    spec="./spec.yaml",                 # path or URL to the OpenAPI document
    package="my_sdk",                   # python package name
    base_url="https://api.example.com", # default API host
    project_dir=".",                    # where the SDK project is written
    auth=OAuthClientCredentials(token_url="https://auth.example.com/oauth2/token"),
    pagination=CursorPagination(),
    errors=NestedError(),
    facade=Facade(),
    # apply_generic_patches=True        # apostrophe / lenient enums / oneOf first-match (default on)
)

def preprocess(spec):                   # optional: spec-specific quirks via framework helpers
    from sdkgen.preprocess import hoist_items, tag_operations
    hoist_items(spec, [("SomeControl", "items", "SomeEntry")])
    tag_operations(spec, [("/v1/things", "get", "ListThings", "Things")])

def patch(pkg_dir):                     # optional: extra codegen fixups on the generated package
    ...
```

Set a component to `None` to skip vendoring it (e.g. `auth=None`). `facade` defaults on.

## Build pipeline
`load sdk.py` → fetch/pin jar → **preprocess** (generic transforms + your `preprocess`) →
**generate** (OpenAPI Generator) → **patch** (generic patches + your `patch`) →
**vendor** (render selected component templates → `<package>/extras/`, write `_about.py`
provenance) → **smoke** (import every module + count operations).

## Component param reference
Each component is a dataclass whose fields are inlined into a Jinja template at vendor time.

### `OAuthClientCredentials` → `extras/auth.py`
OAuth2 client-credentials grant (Basic creds, form body), auto-refreshing token.

| field | default | meaning |
|-------|---------|---------|
| `token_url` | — (required) | token endpoint |
| `scope_env` | `"SCOPE"` | env var read for the OAuth scope |
| `client_id_env` | `"CLIENT_ID"` | env var for the client id |
| `client_secret_env` | `"CLIENT_SECRET"` | env var for the client secret |
| `base_url_env` | `"BASE_URL"` | env var that overrides `base_url` at runtime |
| `config_class_name` | `"SdkConfiguration"` | name of the generated `Configuration` subclass |
| `retry_statuses` | `(429,500,502,503,504)` | statuses retried by urllib3 |
| `backoff_factor` | `0.5` | retry backoff factor |

### `CursorPagination` → `extras/pagination.py`
Cursor paging: items under `data_field`, cursor under `page_info`.

| field | default | meaning |
|-------|---------|---------|
| `data_field` | `"data"` | response attribute holding the page items |
| `page_info_field` | `"page_info"` | response attribute holding paging info |
| `cursor_field` | `"cursor"` | next-page cursor attribute on page_info |
| `has_next_field` | `"has_next_page"` | boolean attribute on page_info |

### `NestedError` → `extras/errors.py`
Helpers over the generated typed exceptions; extracts a message from `body[error_field][message_field]`.

| field | default | meaning |
|-------|---------|---------|
| `error_field` | `"error"` | top-level error object key |
| `message_field` | `"message"` | message key inside the error object |
| `code_field` | `"code"` | code key inside the error object |

### `Facade` → `extras/facade.py`
Binds each generated `*Api` class as `client.<resource>` and exposes `client.paginate(...)`.
Resources are discovered from the generated `api/` package (alphabetical) — no params.

## Custom components
A component is `{param dataclass, Jinja template, interface}`. To add one, write a dataclass
with a `template` field pointing at your `.jinja`, implement the relevant `extras/` contract,
and reference your class from `sdk.py` (it's just Python — import it).

## Provenance
Every build writes `<package>/_about.py` with `SPEC_VERSION`, `SDKGEN_VERSION`, and
`OPENAPI_GENERATOR_VERSION` for traceability.
