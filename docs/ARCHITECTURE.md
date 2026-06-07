# Architecture — `phantasos`: a multi-spec Python SDK generation framework

Status: **proposal** (no refactor yet). Captures the decisions from the architecture
review for turning this single-spec generator into a reusable framework. Prisma Browser
is the first SDK; the framework must serve **arbitrary** OpenAPI specs.

## 1. Decisions (from review)
| # | Decision | Choice |
|---|----------|--------|
| Breadth | What specs? | **Arbitrary** OpenAPI specs; auth/pagination/errors are **pluggable components** |
| Distribution | Where does code live? | Framework = **pip-installable CLI**; each SDK in its **own repo**, built via `phantasos build ./sdk.py` |
| Coupling | How do components reach an SDK? | **Vendored** — copied into the SDK's `extras/`; SDK is self-contained (deps: httpx/pydantic/urllib3 only) |
| Config | How is a spec described? | **Per-spec Python module** (`CONFIG = SdkConfig(...)` + optional `preprocess`/`patch` hooks) |
| Params | How do per-spec params reach components? | **Templated** (Jinja) — constants inlined at vendor time; framework keeps the templates |
| Versioning | SDK version? | **Independent semver** per SDK (hand-bumped); spec/framework/jar versions recorded in metadata |
| CLI | Surface? | **Minimal**: `phantasos build [config]`; jar auto-fetched/pinned to `~/.cache/phantasos`; Java checked |

## 2. The three specificity layers (what drives the split)
Today everything lives in one repo. The re-arch separates code by **how reusable it is**:

1. **Framework-generic** (any spec) → `phantasos/` package:
   - Spec transforms: `allOf`-of-non-object collapse, mojibake repair, enum-dedupe.
   - Codegen patches: apostrophe-enum re-quote, **lenient enums** (str+int), **oneOf first-match**.
   - Mechanics: jar fetch/pin, OAG invocation, smoke (import + op count), facade *pattern*.
2. **Components** (reusable, vendored+templated, selected per spec) → `phantasos/components/`:
   - `auth/` (e.g. `oauth_client_credentials`), `pagination/` (e.g. `cursor`),
     `errors/` (e.g. `nested_error`), `facade/` (resource binding).
   - Each = **{interface, Jinja template(s), param dataclass}**.
3. **Spec-specific** (one spec only) → that spec's `sdk.py` + hooks:
   - Spec source, package name, base URL, component **selections + params**, and
     custom `preprocess`/`patch` hooks (e.g. prisma-browser's schema hoists + op tagging).

## 3. What's hard-coded today → where it goes
| Hard-coded now | Location now | Destination |
|---|---|---|
| `SPEC_SRC`, `OUT`, `PKG`, base URL | `Makefile` | spec `sdk.py` → `SdkConfig` |
| allOf-collapse, mojibake, enum-dedupe | `preprocess_spec.py` | `phantasos` generic transforms (reusable helpers) |
| `HOISTS`, `USER_REQUEST_OPS` | `preprocess_spec.py` | spec `sdk.py` `preprocess()` hook (calls framework helpers) |
| apostrophe / lenient-enum / oneOf patches | `apply_patches.py` | `phantasos` generic patches (default-on) |
| `PrismaSaseConfiguration`, `token_url`, `scope=tsg_id`, `auth.apps...`, `DEFAULT_BASE_URL` | `overlay/auth.py` | `auth/oauth_client_credentials` **component template** + params in spec `sdk.py` |
| `.data`/`page_info.cursor` assumptions | `overlay/pagination.py` | `pagination/cursor` component (params: data_field, cursor_path, has_next_path) |
| `{error:{message}}` extraction | `overlay/errors.py` | `errors/nested_error` component (params: message/code path) |
| resource→Api binding | `overlay/facade.py` | `facade` component (generic; derived from generated `api/`) |

## 4. Target layout
**Framework repo (this one, slimmed):**
```
phantasos/
  __init__.py            # build(config) public API
  cli.py                 # `phantasos build [config]`
  config.py              # SdkConfig + component param dataclasses
  generate.py            # jar fetch/pin + OAG invocation
  preprocess.py          # generic transforms (collapse/mojibake/dedupe) as helpers
  patches.py             # generic codegen patches (apostrophe/lenient/oneOf)
  smoke.py               # import + op-count check
  components/
    auth/oauth_client_credentials.py.jinja
    pagination/cursor.py.jinja
    errors/nested_error.py.jinja
    facade/client.py.jinja
    _interfaces.py        # AuthProvider / Paginator / ErrorMapper contracts
tests/                   # framework + template-render tests
docs/
pyproject.toml           # console_scripts: phantasos = phantasos.cli:main
```
**A spec repo (e.g. prisma-browser, lives elsewhere):**
```
sdk.py                   # CONFIG = SdkConfig(...); def preprocess/patch (optional)
spec.yaml                # the OpenAPI spec (or a URL in CONFIG)
prisma_browser/          # GENERATED (committed or gitignored, per that repo)
  ... api/ models/ extras/(vendored components) _about.py
pyproject.toml           # name + hand-bumped semver
CHANGELOG.md
.env.example
```

## 5. `SdkConfig` (illustrative)
```python
from phantasos import SdkConfig
from phantasos.components.auth import OAuthClientCredentials
from phantasos.components.pagination import CursorPagination
from phantasos.components.errors import NestedError

CONFIG = SdkConfig(
    spec="./spec.yaml",
    package="prisma_browser",
    base_url="https://api.sase.paloaltonetworks.com",
    auth=OAuthClientCredentials(
        token_url="https://auth.apps.paloaltonetworks.com/oauth2/access_token",
        scope_env="SCOPE", basic_auth=True,
    ),
    pagination=CursorPagination(data_field="data",
                                cursor_path="page_info.cursor",
                                has_next_path="page_info.has_next_page"),
    errors=NestedError(message_path="error.message", code_path="error.code"),
    facade=True,
    # generic patches (apostrophe/lenient/oneOf) default-on
)

def preprocess(spec):       # spec-specific quirks, via framework helpers
    from phantasos.preprocess import hoist_items, tag_operations
    hoist_items(spec, [("AllowedOrBlockedExtensionsControl", "extensions",
                        "AllowedOrBlockedExtensionEntry"), ...])
    tag_operations(spec, [("/seb-api/v1/user-requests", "get", "ListUserRequests",
                           "User Requests"), ...])
```

## 6. `phantasos build` pipeline
load `sdk.py` → fetch/pin jar → **preprocess** (generic helpers + `CONFIG.preprocess`)
→ **generate** (OAG, package/flags from CONFIG) → **patch** (generic + `CONFIG.patch`)
→ **vendor** (render selected component templates with params → `extras/`; write `_about.py`
provenance: spec version, framework version, jar version) → **smoke** (import + op count).

## 7. Component contract
A component is `{param dataclass, Jinja template(s), interface}`:
- **AuthProvider** → renders `extras/auth.py`: builds an authenticated client/`Configuration`.
- **Paginator** → renders `extras/pagination.py`: `paginate(list_method, **filters)`.
- **ErrorMapper** → renders `extras/errors.py`: typed-exception helpers + message extraction.
- **Facade** → renders `extras/facade.py`: binds generated `*Api` classes as `client.<resource>`.
Custom components: provide a param dataclass + template implementing the interface; reference
it from `sdk.py` (it's Python — just import your class).

## 8. Risks
- **Over-abstraction before a 2nd spec.** Mitigation: build only what SASE needs now; the
  parity gate (reproduce today's prisma-browser SDK) keeps scope honest; revisit interfaces
  when a genuinely different spec arrives.
- **Template maintenance.** Vendored+templated means component code lives in `.jinja`, not
  directly importable — mitigate with template-render unit tests.
- **Interface churn.** The pluggable contracts (auth/pagination/errors) are first-draft; a
  non-SASE spec may force revisions. Accepted; design for extension, validate with spec #2.
