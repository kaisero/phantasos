# product-config

Validated against ca087e7 on 2026-06-14 · Purpose: how a product's `sdk.yml` (and optional `cli.yml`, `hooks.py`, `overrides/`) is declared, loaded, and converted into a `LoadedProduct` that drives every downstream build stage.

## Purpose & responsibilities

`productconfig.py` is the single entry point that reads a product directory and
produces a fully-validated `LoadedProduct`: parsed + validated `ProductConfig`,
resolved component models (auth / pagination / errors / facade / retry), a
complete Jinja `context` dict, and resolved paths (`spec_path`, `output_dir`).
`config.py` holds the pydantic component models and the five built-in registries
the loader dispatches against.

## How it works

`load_product(name_or_path)` in `productconfig.py` is the only public entry
point. It runs in one pass:

1. **Path resolution** — accepts a product name (`products/<name>/sdk.yml`) or a
   direct path to an `sdk.yml` file; resolves to an absolute `base_dir`.
2. **Parse + validate** — `_read_yaml(sdk_path)` (ruamel.yaml, safe mode) then
   `ProductConfig(**data)` (pydantic, `extra="forbid"`). Unknown keys raise
   `ValidationError` at parse time.
3. **Component resolution** — `resolve_component(block, registry, base_dir)` for
   each of `auth`, `pagination`, `errors`, `facade`, `retry`. The dispatcher
   checks the `type` field: a `./`-prefixed path or `.jinja` suffix → `CustomComponent`
   (extra fields forwarded as template vars); a string name → looked up in the
   relevant `BUILTIN_*` registry (e.g. `BUILTIN_AUTH`) in `config.py`; missing
   → `ValueError`. `facade`/`retry` default to `true` in `sdk.yml`, which the
   loader normalises to `{"type": "default"}`.
4. **Spec info** — reads `info.title` and `info.version` from the OpenAPI doc
   (skipped gracefully if the spec file doesn't yet exist).
5. **Jinja context** — assembled from the resolved fields and `cfg.vars`. The
   `_AUTO_EXPOSED` set in `productconfig.py` lists the names that are always
   injected; `cfg.vars` keys that collide raise `ValueError`.
6. **`include:` validation** — each source path is verified to exist and to stay
   within `base_dir` (path traversal rejected here, not at render time).
7. Returns `LoadedProduct` (dataclass): `config`, `base_dir`, `spec_path`,
   `output_dir`, the five resolved component objects, and `context`.

### Jinja context keys (auto-exposed)

`package`, `library`, `base_url`, `spec_version`, `spec_title`, `has_auth`,
`has_pagination`, `has_errors`, `has_facade`, `config_class_name`. (`has_retry` is
also injected into the context but is **not** in `_AUTO_EXPOSED`, so a `vars` key
of that name silently shadows it — a gap in the collision guard, not protection.)
When `project:` is present: `distribution`, `description`, `author`,
`author_email`, `repo_url`, `license`, `python_versions`, `dependencies`.
`cfg.vars` entries are merged last (collisions with auto-exposed names are
rejected).

## Product directory layout

```
products/<name>/
├── openapi.yml                  # OpenAPI source (or set sdk.yml `spec:`)
├── sdk.yml                      # required — build config (see AUTHORING_A_SPEC.md)
├── cli.yml                      # optional — CLI classifier overrides
├── overrides/
│   ├── README.md.jinja          # required — becomes the SDK's README
│   └── tests/                   # optional — per-product integration tests
└── hooks.py                     # optional — preprocess(spec)/patch(pkg_dir) hooks
```

`openapi.yml`, `sdk.yml`, and `overrides/README.md.jinja` are required. All other
files are optional.

### `sdk.yml` field summary

| Field | Required | Default | Notes |
|---|---|---|---|
| `package` | yes | — | Python package name (snake_case) |
| `output` | yes | — | SDK output path (relative to `sdk.yml`) |
| `base_url` | yes | — | Default API host for component templates |
| `spec` | no | `"./openapi.yml"` | OpenAPI doc path (relative to `sdk.yml`) |
| `apply_generic_patches` | no | `true` | Apostrophe-enum / lenient-enum / oneOf first-match |
| `generator.library` | no | `"urllib3"` | OAG HTTP library |
| `generator.oneof_discriminator_lookup` | no | `true` | OAG discriminator dispatch |
| `auth` | no | omitted | Component block; `type` selects built-in or custom template |
| `pagination` | no | omitted | Component block |
| `errors` | no | omitted | Component block |
| `facade` | no | `true` | `true` → `{type: default}`; `false`/omit → skip |
| `retry` | no | `true` | `true` → `{type: default}`; `false`/omit → skip |
| `transforms.hoist` | no | `[]` | Hoist inline array-item schemas to named components |
| `transforms.tag_operations` | no | `[]` | Assign operationId + tag to path+method |
| `hooks` | no | omitted | Path to `hooks.py` (relative to `sdk.yml`) |
| `vars` | no | `{}` | Extra Jinja context; must not shadow auto-exposed names |
| `include` | no | `{}` | Extra templates → `extras/<dest>` |
| `project` | no | omitted | Required for scaffold; drives `pyproject.toml`, workflows |

### Built-in component types (from `config.py`)

| Category | `type` name | Model | Key fields |
|---|---|---|---|
| `auth` | `oauth_client_credentials` | `OAuthClientCredentials` | `token_url`, `scope_env`, `client_id_env`, `client_secret_env`, `base_url_env`, `config_class_name` |
| `pagination` | `cursor` | `CursorPagination` | `data_field`, `page_info_field`, `cursor_field`, `has_next_field` |
| `errors` | `nested` | `NestedError` | `error_field`, `message_field`, `code_field` |
| `facade` | `default` | `Facade` | (no config fields) |
| `retry` | `default` | `RetryConfig` | `max_retries`, `backoff_base`, `backoff_max`, `jitter_frac`, `statuses`, `respect_retry_after` |

Custom template: set `type` to a relative path ending in `.jinja` → resolved to
`CustomComponent`; all other keys pass through as template vars.

## Build / run pointers

- **Build an SDK:** `phantasos sdk build <name>` (resolves `products/<name>/sdk.yml`)
  or pass a direct path to any `sdk.yml`.
- **CLI stub (pre-build):** `phantasos cli discover <name>` — calls `load_product`
  then inspects the built SDK; requires the SDK to be importable (build first).
- **Tests:** `uv run nox -s gate` (offline); the relevant test file is
  `tests/test_productconfig.py` and `tests/test_config.py`.
- **Field reference:** `docs/AUTHORING_A_SPEC.md`; onboarding walkthrough:
  `docs/ONBOARDING.md`.

## Public API

<!-- GENERATED:api -->
- `productconfig.py`
  - class `ProjectConfig`
  - class `Hoist`
  - class `TagOperation`
  - class `Transforms`
  - class `GeneratorConfig` — OpenAPI Generator invocation options (sdk.yml `generator:` block).
  - class `ProductConfig`
  - class `CustomComponent` — A component backed by a per-product template path (arbitrary config).
  - `resolve_component(block, registry, base_dir)` — Turn a raw sdk.yml component block into a validated component model.
  - class `LoadedProduct`
  - `load_product(name_or_path)`
<!-- /GENERATED:api -->

## Gotchas / invariants

- **`extra="forbid"` everywhere.** Unknown `sdk.yml` keys raise `ValidationError`
  immediately; there is no silent ignore. This is the primary guard against typos
  (e.g. `pagintion` instead of `pagination`).
- **`facade`/`retry` default to `true` in sdk.yml** — the loader normalises `True`
  to `{"type": "default"}` before calling `resolve_component`. Omitting these keys
  still results in a resolved component unless explicitly set to `false`.
- **`vars` collision guard.** Any `vars` key in the `_AUTO_EXPOSED` set raises
  `ValueError` from `load_product`, not a silent override.
- **`include:` path traversal rejected at load time**, not render time — sources
  must be relative to and within `base_dir`.
- **`spec:` is allowed to not exist yet** — `load_product` tolerates a missing
  spec file (returns empty `info`); a build will fail later when OAG tries to read
  it.
- **`hooks:` is declared but not loaded here.** `load_product` validates the path
  field exists in the YAML but does not import `hooks.py`. The SDK build stage
  (`generator/sdk/build.py`) imports it.
- **`_BASE_DEPS`** in `productconfig.py` is the default runtime dependency list
  baked into `ProjectConfig.dependencies`; overridable per-product in `sdk.yml`.

## See also

- Field reference: `docs/AUTHORING_A_SPEC.md`
- Onboarding: `docs/ONBOARDING.md`
- Component templates: `.agents/context/components.md` (when written)
- SDK build pipeline: `.agents/context/sdk-generator.md`
- Design: `docs/specs/2026-06-14-agents-context-docs-design.md`
