# Design: Declarative per-product config (`products/<product>/sdk.yml`) — Phase 1 (A+B)

**Date:** 2026-06-07
**Status:** Draft for review
**Branch:** `declarative-products-config` (off `main`)

## Context & scope

Today each product is a Python module `transformations/<product>.py` that builds an
`SdkConfig(...)` and may define imperative `preprocess(spec)` / `patch(pkg_dir)` hooks; its
OpenAPI doc lives at `specs/<product>.yml`. We are replacing this with a **declarative
YAML** model and a self-contained per-product directory.

This redesign was scoped (via grilling) into three sequenced sub-projects:

- **A — declarative config:** the `sdk.yml` schema + loader + validation, replacing the
  Python module.
- **B — per-product template augmentation:** a per-product `templates/` dir, a `vars`
  substitution store, and an `include` map of extra templates vendored into the SDK.
- **C — SDK project scaffolding (DEFERRED):** emit phantasos's own CI/CD, packaging,
  pre-commit, and docs infra into each generated SDK with value substitution. **Not in this
  spec.** The `.openapi-generator-ignore` / "omit OAG scaffolding files" topic also belongs
  to C.

**This spec covers A+B together** (they share the `sdk.yml` schema and the template
pipeline). C is a separate spec/plan later.

## Directory layout

```
products/<product>/
├── openapi.yml      # the raw OpenAPI document (moved from specs/<product>.yml)
├── sdk.yml          # THE declarative config: build settings + components + vars + include
├── templates/       # per-product Jinja files referenced by sdk.yml (custom types / include)
│   └── *.jinja
└── hooks.py         # OPTIONAL linked escape hatch (arbitrary preprocess/patch)
```

`specs/` is removed (its docs move into each product dir as `openapi.yml`). The two existing
products — `adem`, `prisma-browser` — are migrated to this layout.

## `sdk.yml` schema

```yaml
# ---- build config (also auto-exposed to the template namespace) ----
package: prisma_browser                  # python package name
output: ../prisma-browser-sdk            # where the SDK is written (relative to product dir)
library: urllib3                         # OAG python library
spec: ./openapi.yml                      # default; convention is openapi.yml in this dir
apply_generic_patches: true

# ---- declarative spec transforms (run BEFORE hooks.py) ----
transforms:
  hoist:
    - {schema: AllowedOrBlockedExtensionsControl, field: extensions, item: AllowedOrBlockedExtensionEntry}
  tag_operations:
    - {path: /seb-api/v1/user-requests, method: get, operation_id: ListUserRequests, tag: User Requests}

# ---- optional linked Python escape hatch ----
hooks: ./hooks.py                        # defines preprocess(spec) / patch(pkg_dir); runs after transforms

# ---- typed components (validated; type = built-in name OR ./templates/x.jinja) ----
auth:
  type: oauth_client_credentials
  token_url: https://auth.apps.paloaltonetworks.com/oauth2/access_token
  base_url: https://api.sase.paloaltonetworks.com
  scope_env: SCOPE
  base_url_env: PRISMA_SASE_BASE_URL
  config_class_name: PrismaSaseConfiguration
pagination:
  type: cursor
  data_field: data
  cursor_field: cursor
  has_next_field: has_next_page
errors:
  type: nested
facade: true

# ---- supplemental substitution variables (extras ONLY; collision with auto-exposed = error) ----
vars:
  support_email: sdk@example.com

# ---- arbitrary extra templates vendored into <package>/extras/ (dest -> source) ----
include:
  extras/retry.py: ./templates/retry.py.jinja
```

### Template namespace (single source of truth)

The template rendering context is assembled once and shared by all component/`include`
templates:

- **build-config fields** (`package`, `library`, `base_url` …) — auto-exposed.
- **spec-derived metadata** — `spec_version`, `spec_title` (read from `openapi.yml`).
- **component config** — each component's resolved fields (e.g. `config_class_name`).
- **`vars`** — supplemental values. phantasos **fails fast** if a `vars` key shadows any
  auto-exposed name.

### Components

- `auth`, `pagination`, `errors`, `facade` are **typed** with known config schemas (validated).
- `type:` resolves to a **built-in** strategy name (→ a bundled template) or a **per-product
  template path** (`./templates/foo.jinja`) for a novel scheme.
- Built-in strategies and their bundled templates are preserved 1:1 with today:
  `oauth_client_credentials`, `cursor`, `nested`, plus `facade`.

### `include`

- A map of **destination → source**: destination is restricted to **`<package>/extras/`**
  (reject any path escaping it); source is a Jinja file (typically under the product's
  `templates/`).
- Rendered with the same shared context as components.

## Validation (pydantic v2)

phantasos takes a **pydantic v2** dependency (a build-time tool dep — distinct from the
generated SDK's runtime deps). The schema is modeled as pydantic models:

- Required vs optional fields, types, **unknown-key rejection** (`extra="forbid"`).
- A discriminated/typed union for each component (built-in `type` enum **or** a template
  path), with per-type config validation.
- A validator that a custom `type:`/`include:` template path **exists**.
- A validator that no `vars` key collides with an auto-exposed name.
- Clear, located error messages (pydantic's default) surfaced by the CLI.

The existing dataclass components (`OAuthClientCredentials`, `CursorPagination`,
`NestedError`, `Facade`) are reworked into this pydantic model layer.

## Component template rewrite (adapt-to-contract only)

The 4 bundled component templates are **rewritten to consume the new unified context**
(auto-exposed values + `vars`), replacing the ad-hoc `flags` dict that `render.py` builds
today. **Generated output is preserved** — the `prisma-browser-sdk` behavioral suite
(`test_models/auth/pagination/errors/facade/lenient_enums`) is the guardrail and must stay
green. No behavioral redesign of what they emit (that would be a separate effort).

## CLI & build pipeline

- `phantasos build <product-name>` → resolves `products/<product-name>/sdk.yml`. An explicit
  path to a `sdk.yml` is also accepted.
- The Python-module loader (`_load_spec_module`, `importlib`) is **removed**.
- `build()` is refactored to take the loaded, validated config object; pipeline order
  becomes: load+validate `sdk.yml` → preprocess (declarative `transforms` → linked
  `hooks.py` `preprocess`) → generate → patch (generic → linked `hooks.py` `patch`) → vendor
  (components + `include`, shared context) → provenance → smoke.

## Migration

- Move `specs/adem.yml` → `products/adem/openapi.yml`; `specs/prisma-browser.yml` →
  `products/prisma-browser/openapi.yml`.
- Author `products/<product>/sdk.yml` for each, translating the current `SdkConfig` + the
  `_HOISTS`/`_TAG_OPS` data into `transforms:`.
- prisma-browser's `preprocess` is pure data (hoist/tag) → fully declarative; **no `hooks.py`
  needed**. If adem has imperative bits, move them to `products/adem/hooks.py`.
- Delete `transformations/`. Update `noxfile.py` smoke session and the CI smoke job to
  `phantasos build prisma-browser` / `phantasos build adem`.

## Unchanged

- Java auto-provisioning and the OAG invocation.
- The smoke check contract (the SDK still emits `requirements.txt`).
- `preprocess.py` transform helpers (`hoist_items`, `tag_operations`) — now driven by
  declarative data instead of hand-written tuples.

## Out of scope (Phase C and beyond)

- Scaffolding phantasos's CI/CD, packaging, pre-commit, docs into the SDK.
- Controlling/omitting OAG supporting files (`.openapi-generator-ignore`).
- Any behavioral change to the generated auth/pagination/errors/facade code.
