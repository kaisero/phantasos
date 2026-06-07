# Authoring a product (`products/<product>/sdk.yml`)

`phantasos` builds a vendored, self-contained Python SDK for an OpenAPI spec from a
declarative product directory. Create `products/<product>/` with at minimum:

- `openapi.yml` — the OpenAPI source document (or set `spec:` to point elsewhere)
- `sdk.yml` — the build config described below

Then run:

```bash
phantasos build <product>           # resolves products/<product>/sdk.yml
# or pass a direct path:
phantasos build path/to/sdk.yml
```

The build pipeline: **preprocess** (generic transforms → declarative transforms →
`hooks.py` `preprocess`) → **generate** (OpenAPI Generator) → **patch** (generic patches
→ `hooks.py` `patch`) → **vendor** (render component templates into `<package>/extras/`,
write `_about.py` provenance) → **smoke** (import every module + count operations).

---

## Build-config fields (`sdk.yml`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `package` | string | — (required) | Python package name for the generated SDK |
| `output` | string | — (required) | Path to write the SDK to (relative to `sdk.yml`) |
| `base_url` | string | — (required) | Default API host injected into component templates |
| `library` | string | `"urllib3"` | OpenAPI Generator HTTP library (`urllib3` or `httpx`) |
| `spec` | string | `"./openapi.yml"` | Path to the OpenAPI document (relative to `sdk.yml`) |
| `apply_generic_patches` | bool | `true` | Apply apostrophe-enum, lenient-enum, and oneOf first-match patches |

---

## Components

Each component produces a vendored file under `<package>/extras/`. Set a component to
the built-in type name, a custom template path, or omit it entirely to skip vendoring.

### `auth`

Writes `extras/auth.py`.

**Built-in type: `oauth_client_credentials`**

OAuth2 client-credentials grant (Basic creds, form body), auto-refreshing token.

```yaml
auth:
  type: oauth_client_credentials
  token_url: https://auth.example.com/oauth2/token
  scope_env: SCOPE                    # default: SCOPE
  client_id_env: CLIENT_ID            # default: CLIENT_ID
  client_secret_env: CLIENT_SECRET    # default: CLIENT_SECRET
  base_url_env: BASE_URL              # default: BASE_URL
  config_class_name: SdkConfiguration # default: SdkConfiguration
  retry_statuses: [429, 500, 502, 503, 504]  # default
  backoff_factor: 0.5                 # default
```

### `pagination`

Writes `extras/pagination.py`.

**Built-in type: `cursor`**

Cursor paging: items under `data_field`, cursor under `page_info`.

```yaml
pagination:
  type: cursor
  data_field: data            # default
  page_info_field: page_info  # default
  cursor_field: cursor        # default
  has_next_field: has_next_page  # default
```

### `errors`

Writes `extras/errors.py`.

**Built-in type: `nested`**

Helpers over typed exceptions; extracts a message from
`body[error_field][message_field]`.

```yaml
errors:
  type: nested
  error_field: error     # default
  message_field: message # default
  code_field: code       # default
```

### `facade`

Writes `extras/facade.py`. Binds each generated `*Api` class as
`client.<resource>` and exposes `client.paginate(...)` when pagination is present.
Resources are auto-discovered from the generated `api/__init__.py`.

```yaml
facade: true   # shorthand for type: default (no config fields)
```

### Custom templates

Set any component's `type` to a relative path ending in `.jinja` to use a per-product
template instead of a built-in:

```yaml
auth:
  type: ./templates/api_key.py.jinja
  header_name: X-API-Key
```

phantasos resolves the path relative to `sdk.yml`'s directory, verifies it exists, and
passes all other fields as template variables.

---

## `transforms:`

Declarative spec pre-processing applied before OpenAPI Generator runs.

### `hoist`

Promote an inline `array.items` object to a named schema.

```yaml
transforms:
  hoist:
    - schema: SomeControl   # component schema containing the array
      field: items          # property name of the array
      item: SomeEntry       # new name for the hoisted schema
```

### `tag_operations`

Assign `operationId` and tag to a specific path+method.

```yaml
transforms:
  tag_operations:
    - path: /v1/things
      method: get
      operation_id: ListThings
      tag: Things
```

---

## `hooks: ./hooks.py`

Optional Python module (path relative to `sdk.yml`). Define either or both of:

```python
def preprocess(spec: dict) -> None:
    """Called after declarative transforms, before OpenAPI Generator."""
    ...

def patch(pkg_dir) -> None:
    """Called after generic patches, on the generated package directory."""
    ...
```

Hooks run **after** the declarative `transforms:` block.

---

## `vars:`

Supplemental template variables merged into the Jinja context for all component
templates and `include:` templates.

```yaml
vars:
  support_email: sdk@example.com
  api_version: v2
```

**Reserved names** (auto-exposed by phantasos — must NOT be shadowed):
`package`, `library`, `base_url`, `spec_version`, `spec_title`,
`has_auth`, `has_pagination`, `has_errors`, `has_facade`, `config_class_name`.

---

## `include:`

Copy additional Jinja templates into `<package>/extras/`. Keys are destination
filenames (under `extras/`); values are template paths relative to `sdk.yml`.

```yaml
include:
  banner.py: ./templates/banner.py.jinja
```

Destination paths must stay within `extras/` — path traversal is rejected.

---

## Concrete examples

### `products/prisma-browser/sdk.yml`

```yaml
package: prisma_browser
output: ../../../prisma-browser-sdk
base_url: https://api.sase.paloaltonetworks.com
auth:
  type: oauth_client_credentials
  token_url: https://auth.apps.paloaltonetworks.com/oauth2/access_token
  scope_env: SCOPE
  base_url_env: PRISMA_SASE_BASE_URL
  config_class_name: PrismaSaseConfiguration
pagination: {type: cursor}
errors: {type: nested}
facade: true
transforms:
  hoist:
    - {schema: AllowedOrBlockedExtensionsControl, field: extensions, item: AllowedOrBlockedExtensionEntry}
    - {schema: LaunchingExternalApplicationsControl, field: exceptions, item: ExternalApplicationLaunchException}
  tag_operations:
    - {path: /seb-api/v1/user-requests, method: get, operation_id: ListUserRequests, tag: User Requests}
```

### `products/adem/sdk.yml`

```yaml
package: adem
output: ../../../adem-sdk
base_url: https://api.sase.paloaltonetworks.com
auth:
  type: oauth_client_credentials
  token_url: https://auth.apps.paloaltonetworks.com/oauth2/access_token
  scope_env: SCOPE
  base_url_env: ADEM_BASE_URL
  config_class_name: AdemConfiguration
facade: true
hooks: ./hooks.py
```
