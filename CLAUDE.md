# CLAUDE.md — phantasos architecture & how to add capabilities

phantasos generates **native, modern Python SDKs** from OpenAPI specs. It runs OpenAPI
Generator (OAG, pinned `7.22.0`, `-g python --library urllib3`) and then **enhances** the
output. This file defines the framework every feature must follow. **Read it before adding
functionality — keep the system a consistent framework, not a frankenstein of ad-hoc approaches.**

## The build pipeline (`src/phantasos/__init__.py: build`)

`load sdk.yml → write .openapi-generator-ignore → generate (OAG) → prune OAG junk →
patch (generic + product hooks) → vendor components → scaffold project → provenance → smoke`.

A product is `products/<name>/{openapi.yml, sdk.yml, overrides/, hooks.py?}`; build with
`phantasos build <name>`. The generated SDK is a **disposable artifact** written to a sibling
dir — never hand-edit it; all customization lives in version control here.

## The capability framework: three tiers (pick the LEAST-INVASIVE tier that delivers the
## capability on ALL entry points — facade *and* bare `ApiClient`)

**Tier 1 — `extras/` augmentation (PREFERRED).** Additive composition over public seams or the
facade. Vendored Jinja templates in `src/phantasos/components/<name>/*.jinja` → rendered into the
SDK's `<package>/extras/` by `render.vendor`, configured by a typed component in `sdk.yml`.
Use for: auth, pagination helpers, error helpers, the facade, retry (`JitteredRetry` via the
`configuration.retries` urllib3 seam), branded User-Agent, idempotency headers, webhooks, OTel.
Rule of thumb: if it's expressible as composition over a public seam, it's Tier 1.

**Tier 2 — OAG custom templates.** When a capability must live in the *core generated client and
appear on every path/method* (you cannot reach it from `extras/`): override the specific OAG
`.mustache` file(s). Ship them under `src/phantasos/oag_templates/python/` and pass `-t <dir>` to
OAG (`generate.py`). OAG falls back to its built-in templates for every file you don't ship, so
coupling is bounded to the few files you own. Extract a base template with
`openapi-generator author template -g python` and make the *smallest* edit.
Use for: the typed-error hierarchy (e.g. 429→`RateLimitException` in `exceptions.mustache`),
request/response hooks, raw/streaming responses, per-method options.

**Tier 3 — `patches.py` source surgery.** Post-generation AST/source transforms. Reserve for
**bug-fixes** to OAG output (apostrophe/lenient enums, oneOf first-match) and tiny cross-cutting
escape-hatches — **not** for net-new features.

**Anti-pattern (do not do this):** forcing a core-client capability through `extras/` with
`__getattr__` proxies or monkey-swapping generated internals. That couples to OAG internals
*invisibly and untested* — worse than an explicit Tier-2 template. If you're wrapping every method
of every resource, you're in the wrong tier.

**Async is special → generate twice.** True async needs generated `async def` bodies; an external
wrapper can only fake it. The async story is a *second* OAG generation (`library=asyncio`/`httpx`)
into a sibling package sharing `models/`, exposing `AsyncClient`. Never an external async wrapper.

## The component / config model

- Typed pydantic models in `src/phantasos/config.py` (`extra="forbid"`); registries
  `BUILTIN_AUTH/PAGINATION/ERRORS/FACADE` (+ new ones). `productconfig.ProductConfig` carries the
  `sdk.yml` blocks; `load_product` builds the unified template context (`has_auth`, `has_*`, the
  flattened `project.*`, `vars`). Components resolve via `resolve_component` (built-in `type:` or a
  per-product `./templates/x.jinja`).
- On-by-default components (like `retry`) are modelled `bool | dict = True` (cf. `facade`), disabled
  with `<name>: false`.
- The project scaffold (`src/phantasos/scaffold/` + per-product `products/<p>/overrides/`,
  same-path-wins) renders the SDK's pyproject/CI/pre-commit/tests; built-in component tests live in
  `scaffold/tests/test_<component>.py.jinja`, gated on `has_<component>`.

## Where things live
| Path | What |
|---|---|
| `src/phantasos/components/<name>/*.jinja` | Tier-1 vendored `extras/` templates |
| `src/phantasos/oag_templates/python/*.mustache` | Tier-2 OAG template overrides (passed via `-t`) |
| `src/phantasos/patches.py` | Tier-3 generated-code bug-fix surgery |
| `src/phantasos/scaffold/` | built-in SDK project scaffold (CI, pyproject, tests, …) |
| `products/<name>/` | per-product `sdk.yml` + `overrides/` + `hooks.py` |
| `docs/research/2026-06-08-sdk-feature-gap-analysis.md` | the modern-SDK gap roadmap (git-ignored) |
| `docs/superpowers/specs/` and `…/plans/` | per-feature design specs & implementation plans |

## Before adding a feature
1. Check the **gap report** (the roadmap) and existing **specs/plans** — don't reinvent.
2. Decide the **tier** by the rule above; default to Tier 1, escalate only when the capability must
   live on the core client / every path.
3. Model config as a typed component; add/gate the scaffold test; migrate the example products;
   verify with `nox -s smoke` + the regenerated SDK's own suite.

## Dev
`uv run nox` (lint=ruff, type=mypy strict, tests=pytest+cov). `uv run nox -s smoke` builds the
example SDKs end-to-end (Java auto-provisioned; needs network). Keep generated code untouched
except via Tier 2/3.
