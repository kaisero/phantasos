# PR #33 CI Remediation Plan

**PR:** https://github.com/kaisero/phantasos/pull/33 (`feature/sdk-cleanup` → `develop`)

**Status:** 2 of 12 checks red — **Build smoke (auto-provisioned Java)** and **Tests (Python 3.11/3.12/3.13/3.14)**. Lint, mypy, Build docs, CLI isolated-install smoke, CodeQL, Gitleaks, pip-audit all pass.

## TL;DR — not the docs work

Both failures originate in the branch's **typed-wrapper + product-enrollment** commits (which predate the Tier 0/1 docs session), **not** the reference-docs change. Evidence:
- My docs commits (`9ac4bb5..HEAD`) touch only `examples.py`, `wrapper.py` (docstring threading), `render.py` (one `docs=` arg), `mkdocs.yml.jinja`, context/CHANGELOG/plan, and docs test files — nothing in `products/adem`, the `tests`/`smoke` nox sessions, `test_cli.py`, or any urllib3 path.
- `develop` CI is green; `nox.toml` (which enrolls `adem`/`posture` into smoke) does not exist on `develop` — it is new on this branch (`de71eb7`).
- The docs-specific checks (**Build docs**, **Lint & type-check**) are green.

They surfaced now only because this is the **first CI run on the branch** (it was never pushed until the PR).

---

## Root cause 1 — Build smoke: `adem` cannot build under the wrapper classifier

**Symptom** (reproduced locally — `posture` builds clean, only `adem` fails):
```
phantasos sdk build adem
ERROR: None-classified op agent_controller.'agent_controller_get_agent_metric' maps to no
CRUD object on its api class (candidates: []). Add `sdk.yml operations: {...}`.
```

**Cause.** The branch's object-granular wrapper classifier (`build_wrapper_context` → `_resolve_object`) raises on a None-classified op that has no CRUD anchor on its api class and no `sdk.yml operations:` override. **All 13 of adem's operations** are non-CRUD read endpoints (`<controller>_get_<thing>_(metric|score|properties|traffic|hops)`), so `classify_name` returns None for every one and no api class offers a CRUD anchor. `products/adem/sdk.yml` has **no `operations:` block**. The new `nox.toml [smoke] products = ["prisma-browser", "adem", "posture"]` enrolls adem in the smoke gate, so CI now builds it and hits this. On `develop` (no wrapper classifier, adem not smoke-gated) adem built fine — so this is a branch regression in the wrapper + enrollment work.

Full unmapped set (introspected from the generated adem package):
```
agent_controller.agent_controller_get_agent_metric
agent_controller.agent_controller_get_agent_properties
agent_controller.agent_controller_get_agent_score
application_controller.application_controller_get_application_metric
application_controller.application_controller_get_application_score
internet_controller.internet_controller_get_internet_metric
nav_controller.nav_controller_get_nav_traffic
route_controller.route_controller_get_route_hops
rum_controller.rum_controller_get_rum_metric
rum_controller.rum_controller_get_rum_score
zoom_participant_controller.zoom_participant_controller_get_zoom_participant
zoom_participant_controller.zoom_participant_controller_get_zoom_participant_score
zoom_qos_controller.zoom_qos_controller_get_zoom_qos_metric
```

### Fix options (needs a product-modeling decision — see "Decision required")

- **A1 — Add `operations:` overrides (recommended if adem should expose wrappers).** Add a block to `products/adem/sdk.yml` mapping each op to `{resource: <object>, method: <verb>}` using custom verbs derived from the op names, e.g.
  ```yaml
  operations:
    agent_controller.agent_controller_get_agent_metric: {resource: agent, method: get_metric}
    agent_controller.agent_controller_get_agent_score:  {resource: agent, method: get_score}
    agent_controller.agent_controller_get_agent_properties: {resource: agent, method: get_properties}
    application_controller.application_controller_get_application_metric: {resource: application, method: get_metric}
    application_controller.application_controller_get_application_score:  {resource: application, method: get_score}
    internet_controller.internet_controller_get_internet_metric: {resource: internet, method: get_metric}
    nav_controller.nav_controller_get_nav_traffic:   {resource: nav, method: get_traffic}
    route_controller.route_controller_get_route_hops: {resource: route, method: get_hops}
    rum_controller.rum_controller_get_rum_metric:    {resource: rum, method: get_metric}
    rum_controller.rum_controller_get_rum_score:     {resource: rum, method: get_score}
    zoom_participant_controller.zoom_participant_controller_get_zoom_participant:       {resource: zoom_participant, method: get}
    zoom_participant_controller.zoom_participant_controller_get_zoom_participant_score: {resource: zoom_participant, method: get_score}
    zoom_qos_controller.zoom_qos_controller_get_zoom_qos_metric: {resource: zoom_qos, method: get_metric}
  ```
  Yields `client.agent.get_metric(...)` etc. Verify the override schema/keying against `wrapper.validate_override_keys` (keyed `api_attr.raw_method`) and the memory notes on override-vs-rename ([[cli-override-cannot-classify-unmapped]]). Keeps adem in smoke with real wrappers.
- **A2 — Disable the facade for adem (`facade: false`).** Honest if adem (read-only analytics) shouldn't have CRUD-shaped wrappers. Skips wrapper classification entirely → build passes. **Must verify** the CLI generator tolerates a product with no `_WRAPPERS` (the CLI builds its IR from `_WRAPPERS`/`_bindings`); if it can't, A2 is not viable without further work.
- **A3 — Un-enroll adem from smoke (stopgap).** Remove `"adem"` from `nox.toml [smoke]`. Fastest green, but leaves adem unbuildable under the wrapper and reduces coverage — only as an interim while A1/A2 is decided.

---

## Root cause 2 — Tests: `sdk build` of a facade SDK imports `urllib3`, absent in the `tests` job

**Symptom** (CI, all Python versions; 438 passed, 53 skipped, 1 failed):
```
tests/test_cli.py::test_cli_build_returns_zero_on_success - ModuleNotFoundError: No module named 'urllib3'
  render.py:186 _vendor_resources → opmodel/introspect.py:211 _introspect
    → importlib.import_module("acme.extras.facade")
      acme/extras/facade.py:11:  from .retry import default_retry
      acme/extras/retry.py:8:    from urllib3.util.retry import Retry   → ModuleNotFoundError
```

**Cause.** The branch's wrapper vendoring (`_vendor_resources`) **imports the freshly-generated package's `extras.facade`** to build `_WRAPPERS`. The generated `facade.py` imports `default_retry` from the vendored `retry.py`, which subclasses `urllib3.util.retry.Retry` — so importing the facade of **any** `facade: true` SDK now requires `urllib3` at build time. `urllib3` is a generated-SDK *runtime* dependency, not a phantasos dependency; the **`smoke`** nox session installs the SDK base deps (`uv pip install 'urllib3...' 'python-dateutil...' 'pydantic...' 'typing-extensions...'`), but the **`tests`** session does not. `test_cli_build_returns_zero_on_success` builds a `facade: true` SDK in-process, so its build hits the import and fails. On `develop` (no wrapper-vendoring introspection of the facade) this build path never imported urllib3, so the test was green — branch regression.

Why local runs missed it: my dev env (`/tmp/phantasos-plan`) and even a fresh `uv sync` pull `urllib3` transitively, so the import resolves locally. The CI `tests` job's locked env does not have it. (The test also *passes in isolation* — it only fails in the full suite when run where urllib3 is truly absent.)

### Fix (recommended B1)

- **B1 — Install the SDK base runtime deps in the `tests` nox session**, mirroring `smoke`. The wrapper vendoring is now part of every facade `sdk build`, so tests that build facade SDKs need `urllib3`, `python-dateutil`, `pydantic`, `typing-extensions` importable. Add them to the `tests` session in `noxfile.py` (e.g. the same `session.install(...)`/`uv pip install` the smoke session uses), or to a dedicated `sdk-runtime` dependency group the `tests` session installs.

Alternatives (weaker):
- **B2 — Make the facade import of `retry` lazy** so reading `_WRAPPERS` doesn't import urllib3. Larger change to the facade/retry templates; risks the runtime Client losing its default retry wiring. Not recommended.
- **B3 — Skip `test_cli_build_returns_zero_on_success` when urllib3 is absent.** Hides the gap; the underlying "tests build facade SDKs but lack runtime deps" problem remains for any future build test. Not recommended.

---

## Decision required

**How should `adem` be handled (root cause 1)?** A1 (override all 13 ops → wrappers), A2 (disable facade — verify CLI tolerates no `_WRAPPERS`), or A3 (un-enroll from smoke as a stopgap). This is a product-modeling call on whether adem's analytics endpoints should be exposed as wrappers. Root cause 2's fix (B1) is unambiguous and proceeds regardless.

---

## Remediation tasks

> Each task ends green-verifiable. These are generator/product-config changes on `feature/sdk-cleanup`; the docs work is untouched.

### Task R1 — `tests` job gets SDK runtime deps (root cause 2, B1)
- **File:** `noxfile.py` (the `tests` session, ~line 116).
- Add the SDK base runtime deps to the `tests` session install step (copy the list the `smoke` session uses: `urllib3 >= 2.1.0, < 3.0.0`, `python-dateutil >= 2.8.2`, `pydantic >= 2.11`, `typing-extensions >= 4.7.1`).
- **Verify:** reproduce CI locally — `UV_PROJECT_ENVIRONMENT=/tmp/pp-norun uv sync` into an env, **uninstall urllib3** (`uv pip uninstall urllib3`), confirm `pytest tests/test_cli.py::test_cli_build_returns_zero_on_success` FAILS with the urllib3 error (RED), then apply R1 and confirm GREEN. (Locally the dep sneaks in transitively, so the explicit uninstall is required to mirror CI.)
- Commit: `fix(nox): tests session installs SDK runtime deps for facade build introspection`.

### Task R2 — Resolve `adem` per the chosen option (root cause 1)
- **A1:** add the `operations:` block to `products/adem/sdk.yml` (13 entries above). Verify `uv run phantasos sdk build adem` succeeds (675-style "imported N modules, 0 failures") and `phantasos cli discover adem` classifies all ops. Commit: `fix(adem): classify analytics ops via sdk.yml operations overrides`.
- **A2:** set `facade: false` in `products/adem/sdk.yml`; verify `sdk build adem` AND `cli build adem` both succeed. Commit: `fix(adem): disable facade for non-CRUD analytics product`.
- **A3:** remove `"adem"` from `nox.toml [smoke]`; note the deferral in `CHANGELOG`/the adem config. Commit: `chore(nox): defer adem from smoke gate pending wrapper modeling`.
- Also audit `posture` is clean (it is — builds 46 modules, 0 failures) and re-confirm `prisma-browser`.

### Task R3 — Full local gate + push + confirm CI green
- Run `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s gate` (offline) and `uv run nox -s smoke` (builds all enrolled products incl. adem) — both green.
- Push to `feature/sdk-cleanup`; re-check `gh pr checks 33` until **Build smoke** and **Tests (3.11–3.14)** pass.

## Verification gotchas
- **urllib3 masking:** local envs pull urllib3 transitively; the R1 verification MUST uninstall it (or use `--no-deps`) to reproduce CI red.
- **prisma-browser-sdk presence:** locally the 53 SDK-dependent tests run (sibling SDK built); in CI they skip. Don't be misled by local "492 passed" — the meaningful signal is `nox -s smoke` (builds adem) and a urllib3-free `tests` run.
- **disk/tmpfs:** the `/tmp` tmpfs hits a per-user quota under repeated nox venv builds; clear `/tmp/pytest-of-*` and stale `/tmp/phantasos-*` between heavy runs.
