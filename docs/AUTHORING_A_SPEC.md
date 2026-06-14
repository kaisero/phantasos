# Authoring a product (`products/<product>/sdk.yml`)

`phantasos` builds a vendored, self-contained Python SDK for an OpenAPI spec from a
declarative product directory. Create `products/<product>/` with at minimum:

- `openapi.yml` — the OpenAPI source document (or set `spec:` to point elsewhere)
- `sdk.yml` — the build config described below

Then run:

```bash
phantasos sdk build <product>       # resolves products/<product>/sdk.yml
# or pass a direct path:
phantasos sdk build path/to/sdk.yml
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
| `generator` | block | see below | OpenAPI Generator invocation options (`generator:` section) |
| `spec` | string | `"./openapi.yml"` | Path to the OpenAPI document (relative to `sdk.yml`) |
| `apply_generic_patches` | bool | `true` | Apply apostrophe-enum, lenient-enum, and oneOf first-match patches |

---

## `generator:`

Options passed to the OpenAPI Generator invocation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `library` | string | `"urllib3"` | OpenAPI Generator HTTP library (`urllib3` or `httpx`) |
| `oneof_discriminator_lookup` | bool | `true` | Dispatch oneOf deserialization via the spec's `discriminator` mapping (OAG `useOneOfDiscriminatorLookup`). Without it, oneOf payloads resolve by trial deserialization, which mis-types variants once enums are lenient. Disable only for a spec whose discriminator mapping is wrong. |

```yaml
generator:
  library: urllib3
  oneof_discriminator_lookup: true
```

No-op for specs without `discriminator` blocks (e.g. adem) — those keep trial
deserialization.

---

## Components

Each component produces a vendored file under `<package>/extras/`. Set a component to
the built-in type name, a custom template path, or omit it entirely to skip vendoring.

### `auth`

Writes `extras/auth.py`.

**Built-in type: `scm_oauth`**

Strata Cloud (SCM/SASE) OAuth2 client-credentials grant (Basic creds, form body),
auto-refreshing token. The `token_url` is baked in as
`https://auth.apps.paloaltonetworks.com/oauth2/access_token` — override only if
targeting a different IdP endpoint.

```yaml
auth:
  type: scm_oauth
  # token_url: https://auth.apps.paloaltonetworks.com/oauth2/access_token  # baked default
  scope_env: SCOPE                    # default: SCOPE
  client_id_env: CLIENT_ID            # default: CLIENT_ID
  client_secret_env: CLIENT_SECRET    # default: CLIENT_SECRET
  base_url_env: BASE_URL              # default: BASE_URL
  config_class_name: SdkConfiguration # default: SdkConfiguration
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

## `project:`

The `project:` block is required when building a scaffold (i.e. when phantasos renders
`pyproject.toml`, GitHub workflows, docs, and other project files into the generated SDK).

```yaml
project:
  distribution: my-sdk           # PyPI distribution name (required)
  author: Jane Smith             # (required)
  author_email: jane@example.com # (required)
  repo_url: https://github.com/org/my-sdk  # (required)
  description: "Python SDK for the My API" # default: ""
  license: Apache-2.0            # SPDX id; default: Apache-2.0
  python_versions: ["3.11", "3.12", "3.13", "3.14"]  # default
  dependencies:                  # default: urllib3/python-dateutil/pydantic/typing-extensions
    - "urllib3 >= 2.1.0, < 3.0.0"
    - "python-dateutil >= 2.8.2"
    - "pydantic >= 2.11"
    - "typing-extensions >= 4.7.1"
```

**`dependencies`** — the defaults match what OpenAPI Generator itself would emit for
`generator.library: urllib3`, so you almost never need to override this field. Only set it when
the SDK genuinely needs additional or different runtime deps.

---

## `overrides/`

`products/<product>/overrides/` mirrors the generated SDK tree. Any file placed here at
the same relative path **replaces** the corresponding built-in scaffold template
(same-path-wins). This is how per-product customisation is layered over the shared
`src/phantasos/scaffold/` templates without modifying the scaffold itself.

**`overrides/README.md.jinja`** — required. This becomes the `README.md` of the generated
SDK. The Jinja context exposes all `sdk.yml` values plus the standard phantasos variables
(`package`, `base_url`, `spec_title`, `has_auth`, `has_pagination`, `has_errors`,
`has_facade`, `config_class_name`).

**`overrides/tests/`** — optional. Jinja templates here are rendered into the generated
SDK's `tests/` directory alongside the gated component tests from the built-in scaffold.
Use this for per-product integration, contract, or model-specific tests.

All files in `overrides/` are version-controlled in this repo and are never lost across
regenerations — the generated SDK is a pure build artifact.

---

## Concrete examples

### `products/prisma-browser/sdk.yml`

```yaml
package: prisma_browser
output: ../../../prisma-browser-sdk
base_url: https://api.sase.paloaltonetworks.com
auth:
  type: scm_oauth
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
  type: scm_oauth
  scope_env: SCOPE
  base_url_env: ADEM_BASE_URL
  config_class_name: AdemConfiguration
facade: true
hooks: ./hooks.py
```
