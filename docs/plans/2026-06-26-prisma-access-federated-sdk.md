# Prisma Access Federated SDK — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. All implementation subagents run on **Opus** (max code quality).

**Goal:** Generate `prisma-access-sdk` — one installable Python distribution (`import prisma_access`) federating 12 OpenAPI specs into one sub-package each (`prisma_access.objects`, …), composed by a single top-level `Client` over one shared SCM-OAuth token, one `Configuration`, one connection pool, and one shared OAG runtime.

**Architecture:** Each spec is generated in isolation via OAG `--package-name prisma_access.<slug>` (no spec merge). After the per-sub loop, a **runtime-hoist** pass collapses the 12 duplicated OAG runtimes into one `prisma_access._runtime` (the only package-bound line — `getattr(...models, klass)` — is abstracted to a per-handle `.models` attribute). A **composer** renders `prisma_access/__init__.py`: one `TokenManager`, one `SdkConfiguration`, one `RESTClientObject`/pool, and N thin `_BearerApiClient` handles (each tagged `.models`), injected into each sub-package's existing facade `Client`. Bearer is attached at the transport layer (spec-agnostic). An opt-in MkDocs site loops the sub-packages via a `_SUBPACKAGES` registry. SDK-only; CLI is out of scope but the `_SUBPACKAGES` registry is its forward-compat seam.

**Tech Stack:** Python 3.11+, pydantic v2, Jinja2, ruamel.yaml, **libcst** (rev-2: the runtime-hoist import rewrite), OpenAPI Generator 7.22.0 (vendored jar, urllib3 library), Typer/Rich (existing CLI host), pytest + nox, MkDocs-Material + mkdocstrings.

**Design of record:** `docs/specs/2026-06-25-prisma-access-unified-sdk-design.md` (rev 7). Decisions D1–D10 and §-references below point into it.

---

## Plan rev 2 — review corrections (AUTHORITATIVE; overrides any conflicting task text below)

Two Opus reviews (python-pro: correctness vs the real OAG runtime; ponytail: over-build) found 6 runtime blockers + over-build. These corrections are folded into the tasks; where a task body still reads the old way, **this block wins**.

**Locked decisions (from the grill):**
1. **Runtime hoist uses `libcst`** (not regex). Add `libcst>=1.1` to phantasos's dev/build deps (`pyproject.toml` `[dependency-groups]`). The pass resolves `Import`/`ImportFrom` nodes and rewrites any whose target is in the runtime set `{api_client, configuration, rest, exceptions, api_response}` to **absolute** `prisma_access._runtime.X` — covering every shape (dotted `root.slug.X`, `from root.slug import rest`, relative `from ..exceptions`). Applied over `_runtime/*.py` + every `<slug>/api/*.py` + every `<slug>/extras/*.py`.
2. **Region/tenant headers keep `required_for` fail-loud**, but applied on **`ApiClient.default_headers`** (not `Configuration` — that's a no-op, B6). The composer sets each handle's `.default_headers` from env and raises early if a `required_for` sub-package is built with its env unset.
3. **`skip_validate_spec` moves to `SubPackage`** (only `network_services` sets it; the other 11 keep OAG validation). Drop it from `GeneratorConfig` (revert P0.1's model edit; keep only the `generate.py`/`_oag_cmd` plumbing).
4. **`NormalizeIds` stays an explicit named model**; **drop** `SubPackage.transforms`, the `Composer` component-model option (direct render only, like `extras_init.py`), and `LoadedSubPackage.slug` (redundant with `config.slug`).

**Blocker fixes (objective — apply in the named tasks):**
- **B1 (P1.2):** do **not** regex `ApiClient.__init__`. The hoist adds a class-level default via libcst: `class ApiClient: models = None`. The **composer** sets `ac.models = <slug>.models` per handle (loud `AttributeError` on unset → spec risk #4 fail-loud for free). No `__init__` signature surgery.
- **B2 (P1.2):** the real `api_client.py:32` is `from prisma_browser import rest` (non-dotted, `rest.` used 6×). The libcst pass rewrites this shape too → `from prisma_access._runtime import rest`.
- **B3 (P1.2):** `extras/errors.py` (nested/list_error) does `from ..exceptions import …`; hoist must walk `extras/` and rewrite relative runtime imports to absolute `_runtime` — else every sub-facade import fails. (Bonus: one `ApiException` distribution-wide.)
- **B4 (P1.1/P1.3):** the per-sub loop must **not** vendor the real `auth.py` (it imports `..api_client`/`..configuration`, which hoist deletes). Instead vendor a **1-line `extras/auth.py` shim** per sub: `from prisma_access._auth import api_client_from_credentials, api_client_from_env`. Facade template stays byte-identical; direct sub-package `from_env` still works.
- **B5 (P0.3):** `load_product:235` `base_dir / cfg.spec` → `TypeError` when `spec is None`. Guard: when `cfg.subpackages`, skip the top-level spec read (`spec_path = None`, `spec_version/spec_title = None`); make `LoadedProduct.spec_path: Path | None`.
- **B6 (P3.1):** see decision 2 — apply headers on the ApiClient handle, not Configuration.
- **S1 (P1.3/P2.1):** use **absolute** imports in `_auth.py` and the composer (`from prisma_access._runtime.api_client import ApiClient`), never `.._runtime` (off-by-one — `_auth.py` lives at `prisma_access/_auth.py`).
- **S2 (P1.1):** `vendor()` gains `distribution_root: Path` (= `project_dir`), threaded to `introspect(package, distribution_root)`. For single-spec, `project_dir == pkg_dir.parent`, so behavior is unchanged.
- **S4 (P0.1):** the `_oag_cmd` test must monkeypatch `provision.resolve_java`/`ensure_jar` (they run while building the argv and would hit the network under the offline gate) — mirror `tests/test_generate.py:38-40,58-60`. Mocking jar provisioning ≠ mocking the SUT (allowed).
- **S5 (P1.1/build order):** the federated `build()` branch runs **loop → hoist → shared auth → composer → scaffold(+docs) → provenance → smoke** (composer written last, overwrites OAG's empty parent `__init__`). The P1.1 first-light `sdk.yml` needs a `project:` block + `overrides/README.md.jinja` (build aborts at the scaffold step without them) — these are a P1 prerequisite, not P2.
- **S3/N1:** confirm base-path for **all 12** sub-packages (P1.4/P2 live), since the hoist keeps only the donor's `configuration.py` host settings (F4 fallback is gone, not just unused). The P1.2 test fixture must be **seeded from a captured real OAG `api_client.py`** (real multi-line `__init__`, the line-32 `from pkg import rest`, an `extras/errors.py`) so it fails-before for B1/B2/B3.

**Over-build cuts (apply):** smoke needs only a `_count_operations` `rglob` fix — `_import_walk`'s `walk_packages` already covers all subs in one pass; **drop the `subpackages` param** (P2.3). Extract a `_generate_one(...)` helper for the per-sub loop rather than inlining/duplicating `build()` (P1.1). Add **slug validation** (`[a-z][a-z0-9_]*`, unique) in the `ProductConfig` validator (P0.2) — slug becomes a package/dir/import path (trust boundary). Add a `configuration_from_env()` helper to `_auth.py` so the composer's `from_env` doesn't build-and-discard an ApiClient (P1.3/P2.1).

## Global Constraints

- **Branch/release workflow:** work on `feature/prisma-access-sdk` (already off `develop` @ `e0e0561`). PR `--base develop`, **squash-merge**, changes under `## [Unreleased]` in `CHANGELOG.md`. **Never bump `version`** on a feature PR. Never commit to `main`.
- **Frozen oracles:** never edit any path in `.claude/harness.toml` `protected_globs` to make work pass. If an oracle looks wrong, STOP and surface it.
- **Evidence before assertions:** run the command and show real output before claiming a pass. The offline gate (`uv run nox -s gate`) runs automatically on stop; run `uv run nox -s live` before declaring a phase complete (skips without creds).
- **Never break the single-spec products** (`prisma-browser`, `adem`, `posture`): every change is additive/back-compatible. `tests/test_sdk_build.py`, `tests/test_render.py`, `tests/test_productconfig.py`, `tests/test_scaffold.py` must stay green.
- **OAS version per spec:** each spec is generated alone and keeps its own version (network-services 3.1 builds alone with `skip_validate_spec`; `nullable` preserved). No version unification, no merge.
- **Venvs off `/tmp`:** `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/<name>` and `NOX_ENVDIR=$HOME/.tmp/<name>-nox` for venv-backed nox sessions (this machine's `/tmp` is small tmpfs). Leave pytest's `tmp_path` on the default `/tmp`.
- **Subagent model:** Opus for every implementation/review subagent (never Haiku/cheap tier).
- **Context docs:** after a change to a subsystem, update its `.agents/context/*.md` narrative and run `uv run nox -s context` (`-- --check` must pass). Touch: `sdk-generator.md`, `product-config.md`, `scaffold.md`.
- **`extra="forbid"`** on every `sdk.yml` model — new fields are explicit; unknown keys must keep failing loudly.

## Test commands (use throughout)

- Offline unit suite: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pa uv run pytest <path> -v`
- One offline gate: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pa uv run nox -s gate`
- Real OAG build (slow): `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pa NOX_ENVDIR=$HOME/.tmp/pa-nox uv run nox -s smoke` or `phantasos sdk build prisma-access --no-smoke`
- Mark OAG-jar tests `@pytest.mark.slow` (deselected by `-m "not slow"`); mirror `tests/test_sdk_build.py`.

---

## File Structure

**New source files:**
- `src/phantasos/generator/sdk/runtime.py` — the runtime-hoist pass (P1).
- `src/phantasos/generator/sdk/components/facade/composer.py.jinja` — the top-level composing `Client` + `_SUBPACKAGES` (P2).
- `src/phantasos/generator/sdk/components/auth/bearer_api_client.py.jinja` *(or fold into `scm_oauth.py.jinja`)* — `_BearerApiClient` transport hook (P1).

**Modified source files (with the spec's §8 line targets, verified against current source):**
- `src/phantasos/productconfig.py` — `SubPackage` model; `ProductConfig.subpackages` + `model_validator`; `GeneratorConfig.skip_validate_spec`; `DocsConfig.showcase_subpackage`; per-sub contexts in `load_product`; `LoadedProduct.subpackages`.
- `src/phantasos/generator/sdk/generate.py` — `_oag_cmd`/`generate` gain `skip_validate_spec` (append `--skip-validate-spec` after argv line 93).
- `src/phantasos/generator/sdk/preprocess.py` — `strip_external_tags`, `normalize_operation_ids`; `clean()` calls the former.
- `src/phantasos/generator/sdk/build.py` — per-sub build loop; bug at `:63` (`project_dir / Path(*sub.package.split("."))`); runtime-hoist + composer steps; `_about` per-sub + fix `phantasos_version` at `:109`.
- `src/phantasos/generator/sdk/render.py` — `vendor()` takes a `package` override (sub-package) instead of `loaded.config.package`; bug at `:186` (`introspect(pkg, project_dir)` not `pkg_dir.parent`); auth vendored once at distribution root.
- `src/phantasos/generator/sdk/smoke.py` — count/walk per sub-package.
- `src/phantasos/generator/sdk/docs.py` — `build_docs_context` targets the showcase sub-package.
- `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` — loop `prisma_access._SUBPACKAGES`.
- `src/phantasos/scaffold/pyproject.toml.jinja` — `packages` already includes the tree via `package=prisma_access` (one line, no change needed — verify).
- `src/phantasos/config.py` — (only if composer is modeled as a component) a `Composer` model + `BUILTIN_COMPOSER`. *Default: render composer directly (no model), like `extras_init.py`.*

**New product files:**
- `products/prisma-access/sdk.yml`, `products/prisma-access/overrides/README.md.jinja`, `products/prisma-access/openapi/*.yaml` (12, already present in the working tree).

---

# Milestone P0 — Foundations & config rework

*Goal: the federated `sdk.yml` shape loads and validates; the validation/normalize transforms exist as unit-tested helpers; existing single-spec products are unaffected. No build loop yet.*

### Task P0.1: `GeneratorConfig.skip_validate_spec` → `--skip-validate-spec`

**Files:**
- Modify: `src/phantasos/productconfig.py:97-102` (`GeneratorConfig`)
- Modify: `src/phantasos/generator/sdk/generate.py:64-108` (`_oag_cmd`, `generate`)
- Modify: `src/phantasos/generator/sdk/build.py:55-61` (pass the flag through)
- Test: `tests/test_generate.py`, `tests/test_productconfig.py`

**Interfaces:**
- Produces: `GeneratorConfig.skip_validate_spec: bool = False`; `generate.generate(..., skip_validate_spec: bool = False)`; `_oag_cmd(..., skip_validate_spec: bool)`.

> **Rev-2:** `skip_validate_spec` is NOT on `GeneratorConfig` — it lives on `SubPackage` (P0.2; only `network_services` sets it). This task adds only the `generate.py`/`_oag_cmd` **plumbing**; the per-sub flag is wired in P1.1.

- [ ] **Step 1: Write the failing test** (`tests/test_generate.py`) — mirror the existing monkeypatch (`tests/test_generate.py:38-40,58-60`) so `_oag_cmd` doesn't fetch the jar under the offline gate (S4):

```python
from phantasos.generator.sdk.generate import _oag_cmd
from phantasos.generator.sdk import generate as _gen

def test_skip_validate_spec_flag_present_when_set(monkeypatch):
    monkeypatch.setattr(_gen.provision, "resolve_java", lambda: "java")
    monkeypatch.setattr(_gen, "ensure_jar", lambda: "oag.jar")
    cmd = _oag_cmd("spec.yaml", "/out", "pkg", "urllib3", True, skip_validate_spec=True)
    assert "--skip-validate-spec" in cmd

def test_skip_validate_spec_absent_by_default(monkeypatch):
    monkeypatch.setattr(_gen.provision, "resolve_java", lambda: "java")
    monkeypatch.setattr(_gen, "ensure_jar", lambda: "oag.jar")
    cmd = _oag_cmd("spec.yaml", "/out", "pkg", "urllib3", True, skip_validate_spec=False)
    assert "--skip-validate-spec" not in cmd
```

- [ ] **Step 2: Run → fail** — `pytest tests/test_generate.py -k skip_validate -v` → FAIL (`_oag_cmd` takes no `skip_validate_spec`).

- [ ] **Step 3: Implement.** In `generate.py`, add the param to `_oag_cmd` and `generate`, and append the flag (no `GeneratorConfig` change — the flag is per-`SubPackage`, P0.2):

```python
def _oag_cmd(spec_path, out_dir, package, library, oneof_discriminator_lookup,
             *, skip_validate_spec: bool = False) -> list[str]:
    lookup = "true" if oneof_discriminator_lookup else "false"
    cmd = [ ... unchanged through "RESOLVE_INLINE_ENUMS=true" ... ]
    if skip_validate_spec:
        cmd.append("--skip-validate-spec")
    return cmd

def generate(spec_path, out_dir, package, library="urllib3",
             oneof_discriminator_lookup=True, *, skip_validate_spec=False):
    subprocess.run(
        _oag_cmd(spec_path, out_dir, package, library, oneof_discriminator_lookup,
                 skip_validate_spec=skip_validate_spec),
        check=True, stdout=subprocess.DEVNULL)
```

The build loop passes `skip_validate_spec=sub.config.skip_validate_spec` per sub (wired in P1.1).

- [ ] **Step 4: Run → pass** — `pytest tests/test_generate.py -k skip_validate -v` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): --skip-validate-spec plumbing in generate()"`

### Task P0.2: `SubPackage` model + `ProductConfig.subpackages` + legacy validator

**Files:**
- Modify: `src/phantasos/productconfig.py` (new `SubPackage` model above `ProductConfig`; `subpackages` field; `model_validator`)
- Test: `tests/test_productconfig.py`

**Interfaces:**
- Produces:
  ```python
  class SubPackage(BaseModel):
      model_config = ConfigDict(extra="forbid")
      slug: str                                    # e.g. "objects"; -> prisma_access.objects
      spec: str                                    # path relative to sdk.yml
      normalize_operation_ids: NormalizeIds | None = None   # kept explicit (rev-2 Q4)
      operations: dict[str, OperationOverride] = Field(default_factory=dict)
      skip_validate_spec: bool = False             # rev-2: per-sub (network_services only)
      # NOTE (rev-2): NO `transforms` field — no sub of the 12 needs hoist/tag_operations; re-add when one does.
  ```
  `ProductConfig.subpackages: list[SubPackage] = Field(default_factory=list)`; `ProductConfig.spec` becomes optional (`str | None = None`, default `"./openapi.yml"` restored by the validator only when not federated). A `@model_validator(mode="after")` enforces **exactly one of** `{legacy single-spec, federated subpackages}` **and** validates slugs (rev-2: trust boundary — slug becomes a package/dir/import path): each matches `^[a-z][a-z0-9_]*$` and slugs are unique.
- Consumes: `OperationOverride` (existing import); `NormalizeIds` (P0.5 — define it here or alongside).

- [ ] **Step 1: Write the failing tests** (`tests/test_productconfig.py`)

```python
import pytest
from pydantic import ValidationError
from phantasos.productconfig import ProductConfig

def test_federated_config_parses_subpackages():
    cfg = ProductConfig(
        package="prisma_access", output="../out", base_url="https://h",
        project={"distribution": "prisma-access-sdk", "author": "a",
                 "author_email": "a@b.c", "repo_url": "https://x"},
        subpackages=[
            {"slug": "objects", "spec": "openapi/objects.yaml"},
            {"slug": "ztna_connector", "spec": "openapi/ztna-connector.yaml",
             "normalize_operation_ids": {"strip_suffix": ".v2",
                "dots_to_underscore": True, "unify_separator": "_"}},
        ],
    )
    assert [s.slug for s in cfg.subpackages] == ["objects", "ztna_connector"]
    assert cfg.subpackages[1].normalize_operation_ids.strip_suffix == ".v2"

def test_legacy_single_spec_still_parses():
    cfg = ProductConfig(package="prisma_browser", output="../out",
                        base_url="https://h", spec="./openapi.yml")
    assert cfg.subpackages == []
    assert cfg.spec == "./openapi.yml"

def test_cannot_set_both_spec_and_subpackages():
    with pytest.raises(ValidationError):
        ProductConfig(package="p", output="o", base_url="https://h",
                      spec="./openapi.yml",
                      subpackages=[{"slug": "x", "spec": "x.yaml"}])

def test_rejects_bad_and_duplicate_slugs():       # rev-2: trust-boundary validation
    with pytest.raises(ValidationError):
        ProductConfig(package="p", output="o", base_url="https://h",
                      subpackages=[{"slug": "network-services", "spec": "a.yaml"}])  # hyphen
    with pytest.raises(ValidationError):
        ProductConfig(package="p", output="o", base_url="https://h",
                      subpackages=[{"slug": "objects", "spec": "a.yaml"},
                                   {"slug": "objects", "spec": "b.yaml"}])           # dup
```

- [ ] **Step 2: Run → fail** — `pytest tests/test_productconfig.py -k "federated or legacy or both or slugs" -v` → FAIL.

- [ ] **Step 3: Implement.** Add the `NormalizeIds` and `SubPackage` models and the validator. `NormalizeIds`:

```python
class NormalizeIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strip_suffix: str | None = None
    dots_to_underscore: bool = False
    unify_separator: str | None = None
```

Make `ProductConfig.spec: str | None = None` (drop the literal default), add `subpackages: list[SubPackage] = Field(default_factory=list)`, and:

```python
import re
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")

@model_validator(mode="after")
def _exactly_one_spec_mode(self) -> "ProductConfig":
    federated = bool(self.subpackages)
    explicit_spec = self.spec is not None
    if federated and explicit_spec:
        raise ValueError("set either `spec:` (single-spec) or `subpackages:` (federated), not both")
    if not federated and self.spec is None:
        self.spec = "./openapi.yml"   # restore legacy default
    if federated:                     # rev-2: slug is a package/dir/import path — validate it
        seen: set[str] = set()
        for sub in self.subpackages:
            if not _SLUG_RE.match(sub.slug):
                raise ValueError(f"sub-package slug {sub.slug!r} must match {_SLUG_RE.pattern}")
            if sub.slug in seen:
                raise ValueError(f"duplicate sub-package slug {sub.slug!r}")
            seen.add(sub.slug)
    return self
```

Import `model_validator` from pydantic.

- [ ] **Step 4: Run → pass** — `pytest tests/test_productconfig.py -k "federated or legacy or both or slugs" -v` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(config): SubPackage model + federated/legacy spec validator"`

### Task P0.3: Per-sub-package contexts in `load_product` + `DocsConfig.showcase_subpackage`

**Files:**
- Modify: `src/phantasos/productconfig.py` (`LoadedProduct`, `load_product`, `DocsConfig`)
- Test: `tests/test_productconfig.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class LoadedSubPackage:
      package: str               # "prisma_access.objects"
      spec_path: Path
      context: dict[str, Any]    # per-sub jinja context (package=prisma_access.objects, spec_title, ...)
      config: SubPackage         # carries .slug (no separate slug field — rev 2)
  ```
  `LoadedProduct.subpackages: list[LoadedSubPackage] = field(default_factory=list)` (empty for single-spec products). `LoadedProduct.spec_path: Path | None` (None for federated — B5). Top-level `context["package"]` stays the namespace root (`prisma_access`); `context["distribution"]` = `prisma-access-sdk`.
  `DocsConfig.showcase_subpackage: str | None = None`.
- Consumes: `SubPackage` (P0.2), `cfg.project`, the existing `_AUTO_EXPOSED` keys.
- **B5 guard:** `load_product:235` `spec_path = (base_dir / cfg.spec).resolve()` crashes when `cfg.spec is None` (federated). Wrap it: only read the top-level spec when `not cfg.subpackages`; for federated set `spec_path = None`, `spec_version/spec_title = None`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from phantasos.productconfig import load_product

def test_federated_load_builds_per_sub_contexts(tmp_path):
    # minimal federated product fixture written into tmp_path (sdk.yml + 2 stub specs)
    # ... write sdk.yml with subpackages [objects, posture] and two stub openapi specs ...
    loaded = load_product(str(tmp_path / "sdk.yml"))
    assert loaded.context["package"] == "prisma_access"
    assert loaded.spec_path is None                       # B5: no top-level spec when federated
    subs = {s.config.slug: s for s in loaded.subpackages}
    assert subs["objects"].package == "prisma_access.objects"
    assert subs["objects"].context["package"] == "prisma_access.objects"
    assert subs["objects"].spec_path == (tmp_path / "openapi/objects.yaml").resolve()
```

(The test helper writes a tiny `sdk.yml` + two stub specs into `tmp_path`. Reuse the existing `tests/test_productconfig.py` fixture style — it already writes sdk.yml files into `tmp_path`.)

- [ ] **Step 2: Run → fail** — `pytest tests/test_productconfig.py -k federated_load -v` → FAIL (`LoadedProduct` has no `subpackages`).

- [ ] **Step 3: Implement.** In `load_product`, after building the top-level `context`, when `cfg.subpackages` is non-empty build one `LoadedSubPackage` per entry. Each sub-context is the top-level context **with** `package` overridden to `f"{cfg.package}.{sub.slug}"` and `spec_title`/`spec_version` read from that sub's spec:

```python
# B5: only read a top-level spec for single-spec products
if cfg.subpackages:
    spec_path = None
    spec_version = spec_title = None
else:
    spec_path = (base_dir / cfg.spec).resolve()
    info = (_read_yaml(spec_path) or {}).get("info", {}) if spec_path.exists() else {}
    spec_version, spec_title = info.get("version"), info.get("title")

sub_loaded: list[LoadedSubPackage] = []
for sub in cfg.subpackages:
    sub_spec = (base_dir / sub.spec).resolve()
    sub_info = (_read_yaml(sub_spec) or {}).get("info", {}) if sub_spec.exists() else {}
    sub_ctx = dict(context)
    sub_ctx["package"] = f"{cfg.package}.{sub.slug}"
    sub_ctx["spec_title"] = sub_info.get("title")
    sub_ctx["spec_version"] = sub_info.get("version")
    sub_loaded.append(LoadedSubPackage(
        package=f"{cfg.package}.{sub.slug}",
        spec_path=sub_spec, context=sub_ctx, config=sub))
```

Add `subpackages=sub_loaded` and `spec_path=spec_path` to the `LoadedProduct(...)` return; add the `subpackages` field and change `spec_path` to `Path | None` on the dataclass. Add `showcase_subpackage: str | None = None` to `DocsConfig`. (The existing `context["spec_title"]`/`spec_version` assignment at `productconfig.py:242-243` reads the now-conditional `info` — move those into the `else` branch above.)

- [ ] **Step 4: Run → pass** — `pytest tests/test_productconfig.py -k federated_load -v` → PASS. Then run the full `tests/test_productconfig.py` to confirm legacy products unaffected.

- [ ] **Step 5: Commit** — `git commit -m "feat(config): per-sub-package LoadedProduct contexts + showcase_subpackage"`

### Task P0.4: `preprocess.strip_external_tags`

**Files:**
- Modify: `src/phantasos/generator/sdk/preprocess.py` (new transform + call from `clean`)
- Test: `tests/test_sdk_preprocess.py`

**Interfaces:**
- Produces: `strip_external_tags(spec: Any, stats: dict[str, int]) -> None` — removes a top-level `ExternalTags` key (present in incidents/posture/ztna; trips OAG validation). Called from `clean()`.

- [ ] **Step 1: Write the failing test**

```python
from phantasos.generator.sdk.preprocess import strip_external_tags, clean

def test_strip_external_tags_removes_top_level_key():
    spec = {"openapi": "3.0.0", "ExternalTags": [{"name": "x"}], "paths": {}}
    stats = {}
    strip_external_tags(spec, stats)
    assert "ExternalTags" not in spec
    assert stats.get("external_tags_stripped", 0) == 1

def test_clean_invokes_strip_external_tags():
    spec = {"openapi": "3.0.0", "ExternalTags": [], "paths": {}}
    clean(spec, {})
    assert "ExternalTags" not in spec
```

- [ ] **Step 2: Run → fail** — `pytest tests/test_sdk_preprocess.py -k external_tags -v` → FAIL.

- [ ] **Step 3: Implement.**

```python
def strip_external_tags(spec: Any, stats: dict[str, int]) -> None:
    """Remove the non-standard top-level `ExternalTags` key (trips OAG validation)."""
    if "ExternalTags" in spec:
        del spec["ExternalTags"]
        stats["external_tags_stripped"] = stats.get("external_tags_stripped", 0) + 1
```

Add `strip_external_tags(spec, stats)` to the end of `clean()` (after `fix_strings_and_enums`).

- [ ] **Step 4: Run → pass** — `pytest tests/test_sdk_preprocess.py -k external_tags -v` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): strip top-level ExternalTags in preprocess.clean"`

### Task P0.5: `preprocess.normalize_operation_ids` (ztna rule)

**Files:**
- Modify: `src/phantasos/generator/sdk/preprocess.py` (new parameterized transform — NOT called from `clean`; driven per-sub from the build loop)
- Test: `tests/test_sdk_preprocess.py`

**Interfaces:**
- Produces: `normalize_operation_ids(spec: Any, *, strip_suffix: str | None, dots_to_underscore: bool, unify_separator: str | None, stats: dict[str, int] | None = None) -> None` — rewrites every operation's `operationId` (e.g. `create.connector_group.v2` → `create_connector_group`). Applied per-sub when `SubPackage.normalize_operation_ids` is set.

- [ ] **Step 1: Write the failing test**

```python
from phantasos.generator.sdk.preprocess import normalize_operation_ids

def test_normalize_strips_suffix_and_dots():
    spec = {"paths": {"/cg": {"post": {"operationId": "create.connector_group.v2"},
                              "get":  {"operationId": "list.connector_groups.v2"}}}}
    normalize_operation_ids(spec, strip_suffix=".v2", dots_to_underscore=True,
                            unify_separator="_")
    ops = spec["paths"]["/cg"]
    assert ops["post"]["operationId"] == "create_connector_group"
    assert ops["get"]["operationId"] == "list_connector_groups"
```

- [ ] **Step 2: Run → fail** — `pytest tests/test_sdk_preprocess.py -k normalize -v` → FAIL.

- [ ] **Step 3: Implement.** Walk `spec["paths"][*][<http-method>]["operationId"]`, strip the suffix, replace `.`→`_` (or `unify_separator`), collapse repeats:

```python
_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")

def normalize_operation_ids(spec, *, strip_suffix=None, dots_to_underscore=False,
                            unify_separator=None, stats=None):
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in _HTTP_METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict) or "operationId" not in op:
                continue
            oid = op["operationId"]
            if strip_suffix and oid.endswith(strip_suffix):
                oid = oid[: -len(strip_suffix)]
            if dots_to_underscore:
                oid = oid.replace(".", unify_separator or "_")
            if unify_separator:
                oid = oid.replace("-", unify_separator)
            op["operationId"] = oid
            if stats is not None:
                stats["operation_ids_normalized"] = stats.get("operation_ids_normalized", 0) + 1
```

- [ ] **Step 4: Run → pass** — `pytest tests/test_sdk_preprocess.py -k normalize -v` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): normalize_operation_ids transform (ztna dotted ids)"`

**P0 done when:** `nox -s gate` green; `load_product` parses both legacy and a federated `sdk.yml`; the two transforms are unit-tested; existing products untouched.

---

# Milestone P1 — First light (3 sub-packages, runtime hoist, shared auth)

*Goal: build **objects**, **network_services**, **ztna_connector** standalone through a per-sub loop, hoist the runtime, vendor shared auth, and prove the per-handle `.models` deserialize + one shared pool + transport bearer. De-risks the whole mechanism before the full 12.*

### Task P1.1: Federated build loop + the two surgical bugs

**Files:**
- Modify: `src/phantasos/generator/sdk/build.py` (per-sub loop around generate→patch→vendor→`_about`)
- Modify: `src/phantasos/generator/sdk/render.py:46-51,186` (`vendor(..., package=None)`; introspect root = `project_dir`)
- Test: `tests/test_sdk_build.py` (`@pytest.mark.slow`, gated on the 12 specs present)

**Interfaces:**
- Consumes: `LoadedProduct.subpackages` (P0.3), `generate.generate(..., skip_validate_spec=)` (P0.1), `normalize_operation_ids` (P0.5).
- Produces: `build()` branches — when `loaded.subpackages` is non-empty, it loops each sub via a `_generate_one(...)` helper (rev-2 — extract, don't inline-duplicate the single-spec body). `vendor()` gains keywords `package: str | None = None`, `context: dict | None = None`, and **`distribution_root: Path | None = None`** (rev-2 S2; defaults to `pkg_dir.parent`, so single-spec is unchanged); `_vendor_resources` calls `introspect(package, distribution_root)`. For federated subs `vendor` is called with `package=sub.package`, `context=sub.context`, `distribution_root=project_dir`, **and auth suppressed** (rev-2 B4 — see below).

- [ ] **Step 1: Write the failing test** (slow, real OAG)

```python
import pytest
from pathlib import Path
from phantasos.generator.sdk.build import build
from phantasos.productconfig import load_product

_SPECS = Path(__file__).parent.parent.parent / "phantasos" / "products" / "prisma-access" / "openapi"

@pytest.mark.slow
@pytest.mark.skipif(not (Path("products/prisma-access/openapi/objects.yaml")).exists(),
                    reason="prisma-access specs absent")
def test_first_light_three_subpackages(tmp_path):
    loaded = load_product("prisma-access")          # sdk.yml limited to 3 subs for P1
    res = build(loaded, run_smoke=False)
    root = loaded.output_dir / "prisma_access"
    for slug in ("objects", "network_services", "ztna_connector"):
        assert (root / slug / "__init__.py").exists()
        assert (root / slug / "api").is_dir()
        assert (root / slug / "models").is_dir()
```

- [ ] **Step 2: Run → fail** — `pytest tests/test_sdk_build.py -k first_light -v -m slow` → FAIL (build has no federated branch; sub dirs not emitted at the dotted path).

- [ ] **Step 3: Implement.** Extract a `_generate_one(...)` helper for the preprocess→generate→patch→vendor of one (spec, package); the single-spec path and the federated loop both call it. Key changes:
  - `vendor()` signature: `def vendor(pkg_dir, loaded, *, package=None, context=None, distribution_root=None, suppress_auth=False, wrapper_objects=None)`. Inside, `pkg = package or loaded.config.package`, `ctx = context or loaded.context`, `dist_root = distribution_root or pkg_dir.parent`. `_vendor_resources` calls `introspect(pkg, dist_root)` (rev-2 S2; single-spec `dist_root == pkg_dir.parent`, unchanged). When `suppress_auth`, **skip** `write_component("auth.py", loaded.auth)` and instead write the 1-line shim (B4):
    ```python
    if loaded.auth and not suppress_auth:
        write_component("auth.py", loaded.auth)
    elif loaded.auth and suppress_auth:          # rev-2 B4: federated sub-package shim
        (extras / "auth.py").write_text(
            f"from {root_package}._auth import api_client_from_credentials, api_client_from_env\n",
            encoding="utf-8")
        written.append("auth.py")
    ```
    (`root_package` = `package.split(".")[0]` = `prisma_access`.) The facade template's `from .auth import …` and `extras_init`'s re-export then resolve to the shim; the composer remains the real entry point.
  - The federated loop in `build()`:
    ```python
    for sub in loaded.subpackages:
        sub_spec, sub_yaml = preprocess.load(str(sub.spec_path))
        preprocess.clean(sub_spec, stats)                      # incl. strip_external_tags
        if sub.config.normalize_operation_ids:
            n = sub.config.normalize_operation_ids
            preprocess.normalize_operation_ids(
                sub_spec, strip_suffix=n.strip_suffix,
                dots_to_underscore=n.dots_to_underscore,
                unify_separator=n.unify_separator, stats=stats)
        pp = project_dir / ".phantasos" / f"{sub.config.slug}.yaml"
        pp.parent.mkdir(parents=True, exist_ok=True)
        preprocess.dump(sub_spec, sub_yaml, str(pp))
        generate.generate(str(pp), str(project_dir), sub.package,
                          library=cfg.generator.library,
                          oneof_discriminator_lookup=cfg.generator.oneof_discriminator_lookup,
                          skip_validate_spec=sub.config.skip_validate_spec)   # rev-2: per-sub
        pkg_dir = project_dir / Path(*sub.package.split("."))    # BUG FIX (was project_dir / cfg.package)
        if cfg.apply_generic_patches:
            patches.apply_generic_patches(pkg_dir)
        render.vendor(pkg_dir, loaded, package=sub.package, context=sub.context,
                      distribution_root=project_dir, suppress_auth=True)   # rev-2 B4
        (pkg_dir / "_about.py").write_text(_about_text(sub), encoding="utf-8")
    ```
    No `loaded_for` clone (rev-2) — `vendor` takes `package`/`context`/`distribution_root` directly.
  - `write_openapi_generator_ignore(project_dir)` once before the loop; `prune_suppressed_files` once after.
  - **Build order (rev-2 S5):** federated branch = loop → `hoist_runtime` (P1.2) → shared `_auth.py` (P1.3) → composer (P2.1) → scaffold(+docs) → provenance → smoke. The single-spec path (no `subpackages`) is unchanged.
  - **P1 prerequisite (rev-2 S5):** the first-light `sdk.yml` needs a `project:` block + `products/prisma-access/overrides/README.md.jinja`, or `build()` aborts at the scaffold guard (`build.py:79-89`).

- [ ] **Step 4: Run → pass** — `pytest tests/test_sdk_build.py -k first_light -v -m slow` → PASS. Then re-run `tests/test_sdk_build.py::test_build_emits_wrapper` (the prisma-browser single-spec build) → still PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): federated per-sub-package build loop (+ dotted-path & introspect-root fixes)"`

### Task P1.2: Runtime-hoist pass (`runtime.py`, **libcst**)

> **Rev-2 (decision 1 + B1/B2/B3):** uses `libcst` (semantic import rewrite), NOT regex. Does **not** touch `ApiClient.__init__` — adds a class-level `models = None` default; the composer sets `.models` per handle. Rewrites EVERY runtime-targeting import (dotted, `from pkg import rest`, relative `from ..exceptions`) to absolute `prisma_access._runtime.X`, across `_runtime/` + `<slug>/api/` + `<slug>/extras/`.

**Files:**
- Create: `src/phantasos/generator/sdk/runtime.py`
- Modify: `pyproject.toml` — add `libcst>=1.1` to phantasos's `[dependency-groups]` (generator build dep)
- Modify: `src/phantasos/generator/sdk/build.py` (call `hoist_runtime(project_dir, root_pkg, slugs)` once after the loop, **before** shared-auth render)
- Test: `tests/test_sdk_runtime.py` (new; offline; fixture seeded from a **captured real** OAG `api_client.py` head — real multi-line `__init__`, the `from <pkg> import rest` line, `getattr(<pkg>.models, klass)`, and an `extras/errors.py` with `from ..exceptions import`)

**Interfaces:**
- Produces: `hoist_runtime(project_dir: Path, root_package: str, slugs: list[str]) -> None`. After it runs:
  - `prisma_access/_runtime/{api_client,configuration,rest,exceptions,api_response}.py` exist; **all** their imports of runtime modules are absolute `prisma_access._runtime.X` (incl. the `from prisma_access._runtime import rest` shape — B2).
  - `_runtime/api_client.py`: a class-level `models = None` is inserted into `class ApiClient`; the module-level `import prisma_access.<donor>.models` is dropped; `getattr(prisma_access.<donor>.models, klass)` → `getattr(self.models, klass)`. **`ApiClient.__init__` is untouched** (B1).
  - The 5 files are deleted from every `prisma_access/<slug>/`.
  - Every `prisma_access/<slug>/api/*.py` **and** `prisma_access/<slug>/extras/*.py` import that targets a runtime module is rewritten to absolute `prisma_access._runtime.X` — covering relative `from ..exceptions import …` in `extras/errors.py` (B3) and `from prisma_access.<slug> import rest` in `api_client` (B2). Model imports and facade/auth-shim imports are left alone.

- [ ] **Step 1: Write the failing test** — fixture mirrors REAL OAG shapes (the `prisma-browser-sdk` ones), so it fails-before for B1/B2/B3, not just the happy path:

```python
import importlib, sys
from pathlib import Path
from phantasos.generator.sdk.runtime import hoist_runtime

def _write(p, text): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)

def test_hoist_runtime(tmp_path):
    root = tmp_path / "prisma_access"
    for slug in ("objects", "posture"):
        b = root / slug
        _write(b / "__init__.py", "")
        _write(b / "api_client.py",                       # real OAG shapes:
               f"import prisma_access.{slug}.models\n"
               f"from prisma_access.{slug} import rest\n"              # B2 non-dotted
               f"from prisma_access.{slug}.configuration import Configuration\n"
               f"from prisma_access.{slug}.exceptions import ApiException\n"
               "class ApiClient:\n"
               "    def __init__(\n        self,\n        configuration=None,\n"
               "        header_name=None,\n    ) -> None:\n"            # B1 multi-line, -> None:
               "        self.rest_client = rest.RESTClientObject(configuration)\n"
               "    def _ApiClient__deserialize(self, data, klass):\n"
               f"        klass = getattr(prisma_access.{slug}.models, klass)\n")
        _write(b / "configuration.py", "class Configuration: pass\n")
        _write(b / "rest.py", f"from prisma_access.{slug}.exceptions import ApiException\n"
                              "class RESTClientObject:\n    def __init__(self, c): pass\n")
        _write(b / "exceptions.py", "class ApiException(Exception): pass\n")
        _write(b / "api_response.py", "class ApiResponse: pass\n")
        _write(b / "api" / "__init__.py", "")
        _write(b / "api" / "thing_api.py",
               f"from prisma_access.{slug}.api_client import ApiClient, RequestSerialized\n"
               f"from prisma_access.{slug}.models.thing import Thing\n")
        _write(b / "extras" / "__init__.py", "")
        _write(b / "extras" / "errors.py", "from ..exceptions import ApiException\n")   # B3 relative
        _write(b / "models" / "__init__.py", "")
        _write(b / "models" / "thing.py", "class Thing: pass\n")

    hoist_runtime(tmp_path, "prisma_access", ["objects", "posture"])

    rt = root / "_runtime"
    ac = (rt / "api_client.py").read_text()
    assert "models = None" in ac                                      # B1 class default
    assert "def __init__(" in ac and "-> None:" in ac                 # __init__ untouched
    assert "getattr(self.models, klass)" in ac
    assert "import prisma_access.objects.models" not in ac
    assert "from prisma_access._runtime import rest" in ac            # B2
    assert not (root / "objects" / "api_client.py").exists()
    api = (root / "objects" / "api" / "thing_api.py").read_text()
    assert "from prisma_access._runtime.api_client import ApiClient, RequestSerialized" in api
    assert "from prisma_access.objects.models.thing import Thing" in api   # model import preserved
    err = (root / "objects" / "extras" / "errors.py").read_text()
    assert "from prisma_access._runtime.exceptions import ApiException" in err  # B3
    # and the whole tree imports cleanly:
    sys.path.insert(0, str(tmp_path))
    try:
        importlib.invalidate_caches()
        importlib.import_module("prisma_access._runtime.api_client")
        importlib.import_module("prisma_access.objects.extras.errors")
    finally:
        sys.path.remove(str(tmp_path))
```

- [ ] **Step 2: Run → fail** — `pytest tests/test_sdk_runtime.py -v` → FAIL (`runtime` module missing).

- [ ] **Step 3: Implement `hoist_runtime` with libcst.** A `cst.CSTTransformer` rewrites imports of the 5 runtime modules to absolute `prisma_access._runtime.X`, given the *current file's* package (to resolve relative imports). Rules:
  - **`ImportFrom`** — resolve `relative` level + `module` against the current package to an absolute dotted module `M`:
    - if `M` ends in a runtime name (`prisma_access.<slug>.exceptions`, or relative `..exceptions` → same) → rewrite to `from prisma_access._runtime.<name> import …` (level 0).
    - if `M` is the sub-package itself and an imported **name** is a runtime module (`from prisma_access.<slug> import rest` — B2) → rewrite to `from prisma_access._runtime import rest`.
  - **`Import`** — `import prisma_access.<donor>.models` in api_client → drop (handled below); other `import` left alone.
  - Leave model imports (`…​.models.*`), facade, and the auth shim untouched.

  ```python
  from __future__ import annotations
  from pathlib import Path
  import libcst as cst

  _RUNTIME = {"api_client", "configuration", "rest", "exceptions", "api_response"}
  _FILES = tuple(f"{m}.py" for m in _RUNTIME)

  class _Rewrite(cst.CSTTransformer):
      def __init__(self, root: str, current_pkg: str):
          self.root, self.cur = root, current_pkg            # cur e.g. "prisma_access.objects.extras"
      def _abs(self, level: int, module: str | None) -> str | None:
          if level == 0:
              return module
          parts = self.cur.split(".")
          base = parts[: len(parts) - level] if level <= len(parts) else []
          return ".".join([*base, module]) if module else ".".join(base)
      def leave_ImportFrom(self, node, updated):
          mod = self._abs(len(updated.relative), _dotted(updated.module))
          if mod is None:
              return updated
          tail = mod.rsplit(".", 1)[-1]
          if tail in _RUNTIME:                                # from <...>.rest import X
              return updated.with_changes(relative=[], module=cst.parse_expression(f"{self.root}._runtime.{tail}"))
          if mod == f"{self.root}.{self.cur.split('.')[1]}" and _names_hit_runtime(updated):  # from <pkg> import rest
              return updated.with_changes(relative=[], module=cst.parse_expression(f"{self.root}._runtime"))
          return updated

  def _rewrite_file(path: Path, root: str, current_pkg: str) -> None:
      tree = cst.parse_module(path.read_text(encoding="utf-8"))
      path.write_text(tree.visit(_Rewrite(root, current_pkg)).code, encoding="utf-8")

  def hoist_runtime(project_dir: Path, root_package: str, slugs: list[str]) -> None:
      root = project_dir / Path(*root_package.split("."))
      rt = root / "_runtime"; rt.mkdir(parents=True, exist_ok=True)
      (rt / "__init__.py").write_text("", encoding="utf-8")
      donor = slugs[0]
      for fname in _FILES:                                   # 1. move donor runtime -> _runtime
          src = (root / donor / fname).read_text(encoding="utf-8")
          (rt / fname).write_text(src, encoding="utf-8")
          _rewrite_file(rt / fname, root_package, f"{root_package}.{donor}")
      _abstract_models(rt / "api_client.py", root_package, donor)   # B1 (class default + getattr/self.models)
      for slug in slugs:                                     # 2. delete per-sub runtime files
          for fname in _FILES:
              (root / slug / fname).unlink(missing_ok=True)
      for slug in slugs:                                     # 3. repoint api/ + extras/ imports
          for sub in ("api", "extras"):
              for f in (root / slug / sub).glob("*.py"):
                  _rewrite_file(f, root_package, f"{root_package}.{slug}.{sub}")

  def _abstract_models(path: Path, root: str, donor: str) -> None:
      tree = cst.parse_module(path.read_text(encoding="utf-8"))
      # (a) drop `import <root>.<donor>.models`; (b) getattr(<root>.<donor>.models, klass) -> getattr(self.models, klass)
      #     via a small CSTTransformer (RemoveImport + Attribute rewrite); (c) insert `models = None` as the
      #     FIRST statement of `class ApiClient` — NO __init__ change.
      ...   # implement the three CST edits; test asserts all three landed
  ```

  Helpers `_dotted(module_node)` (CST attribute → dotted str), `_names_hit_runtime(importfrom)` (any imported name in `_RUNTIME`) are ~3 lines each. The implementer fleshes out `_abstract_models`' three CST edits to satisfy the Step-1 assertions (`models = None` present, `getattr(self.models, klass)`, donor models-import gone) — TDD against the real-shape fixture.

  Add `libcst>=1.1` to `pyproject.toml` `[dependency-groups]` and call `hoist_runtime(project_dir, cfg.package, [s.config.slug for s in loaded.subpackages])` in `build()` after the loop, before shared-auth.

- [ ] **Step 4: Run → pass** — `pytest tests/test_sdk_runtime.py -v` → PASS (incl. the import-the-tree assertion).

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): libcst runtime-hoist pass (one _runtime, per-handle .models)"`

### Task P1.3: Shared auth + `_BearerApiClient`

**Files:**
- Modify: `src/phantasos/generator/sdk/components/auth/scm_oauth.py.jinja` (add `_BearerApiClient` + `configuration_from_env`; under a `{% if federated %}` branch, import the runtime via **absolute** `from prisma_access._runtime.api_client import ApiClient` / `…configuration import Configuration` — rev-2 S1, NOT `.._runtime`)
- Modify: `src/phantasos/generator/sdk/build.py` (render the shared auth ONCE to `project_dir/prisma_access/_auth.py` after hoist — direct render, no component model; pass `federated=True` to the template)
- Test: `tests/test_render.py` (offline: render the template with `federated=True` and assert `_BearerApiClient` + `configuration_from_env` + `update_params_for_auth` override + absolute `_runtime` imports)

**Interfaces:**
- Produces: `prisma_access/_auth.py` exporting `TokenManager`, `SdkConfiguration(Configuration)` (Configuration imported absolutely from `prisma_access._runtime.configuration`), `_BearerApiClient(ApiClient)` (ApiClient from `prisma_access._runtime.api_client`), `api_client_from_credentials`, `api_client_from_env`, and **`configuration_from_env(**overrides)` + `configuration_from_credentials(**overrides)` → `SdkConfiguration`** (rev-2 — the composer builds the shared config from these, no throwaway ApiClient). `_BearerApiClient.update_params_for_auth(self, headers, queries, auth_settings, resource_path, method, body, request_auth=None)` unconditionally sets `headers['Authorization'] = f'Bearer {self.configuration.access_token}'` (rev-2 N2: signature confirmed byte-exact vs OAG 7.22.0; works for posture's empty `auth_settings`).

- [ ] **Step 1: Write the failing test** (offline render assertion)

```python
def test_bearer_api_client_overrides_update_params_for_auth():
    from phantasos.generator.sdk import render
    txt = render._render_component_text("auth/scm_oauth.py.jinja",
            {"config_class_name": "SdkConfiguration", "base_url": "https://h",
             "token_url": "https://t", "client_id_env": "CID",
             "client_secret_env": "CSEC", "scope_env": "SCOPE",
             "base_url_env": "BURL", "has_retry": False})
    assert "class _BearerApiClient" in txt
    assert "def update_params_for_auth" in txt
    assert 'Authorization' in txt and "Bearer" in txt
```

*(If no render helper exists, render via Jinja directly in the test against `components/auth/scm_oauth.py.jinja`; the existing `tests/test_render.py` shows the pattern.)*

- [ ] **Step 2: Run → fail** — FAIL (template has no `_BearerApiClient`).

- [ ] **Step 3: Implement.** In `scm_oauth.py.jinja`, gate a `{% if federated %}` branch that imports the runtime **absolutely** (rev-2 S1) and appends the bearer client + a config helper:

```jinja
{% if federated %}from prisma_access._runtime.api_client import ApiClient
from prisma_access._runtime.configuration import Configuration
{% else %}from ..api_client import ApiClient
from ..configuration import Configuration
{% endif %}

# ... existing TokenManager, {{ config_class_name }}(Configuration) ...
{% if federated %}
class _BearerApiClient(ApiClient):
    """Attach the pull-model bearer at the transport layer (spec-agnostic)."""
    def update_params_for_auth(self, headers, queries, auth_settings, resource_path,
                               method, body, request_auth=None):
        headers["Authorization"] = f"Bearer {self.configuration.access_token}"

def configuration_from_env(**overrides) -> {{ config_class_name }}:
    """Build the shared SdkConfiguration from env (composer uses this — no throwaway ApiClient)."""
    # mirror api_client_from_env's credential resolution, return the {{ config_class_name }} (not an ApiClient)
    ...
{% endif %}
```

`api_client_from_credentials`/`api_client_from_env` return `_BearerApiClient(cfg)` in the federated branch. In `build.py`, after `hoist_runtime`, render this template once with `federated=True` to `project_dir/prisma_access/_auth.py` (direct render — no component model, per rev-2). The single-spec products render the same template with `federated=False` (default) → today's per-package `extras/auth.py`, byte-unchanged.

- [ ] **Step 4: Run → pass** — test PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): shared _auth.py + transport-level _BearerApiClient"`

### Task P1.4: First-light verification (real build, de-risk)

**Files:**
- Test: `tests/test_sdk_build.py` (extend the `first_light` slow test) + a live smoke under `products/prisma-access/overrides/tests/` (skips without creds)
- Confirm (not modify): the libcst hoist's three CST edits landed against the **real** OAG `api_client.py` — the P1.2 real-shape fixture should already match, but P1.4 is the real-build cross-check.

**Interfaces:** consumes everything from P1.1–P1.3.

- [ ] **Step 1: Write the verification test** — extend `test_first_light_three_subpackages` to assert, after `build()` + `hoist_runtime`, that:
  - `prisma_access/_runtime/api_client.py` exists and the per-sub `api_client.py` do not;
  - importing the built tree (`on_sys_path`) and constructing two handles `ac = _BearerApiClient(cfg); ac.models = <slug>.models` (rev-2 B1: `.models` is an **instance attribute**, not a ctor arg) for `objects` and `ztna_connector` resolves a model name in each namespace (`getattr(ac.models, "<KnownModel>")` round-trips);
  - both handles share one `RESTClientObject` after composer wiring (`ac_a.rest_client is ac_b.rest_client`).
- [ ] **Step 2: Run → cross-check the real build** — `phantasos sdk build prisma-access --no-smoke` against the 3-sub sdk.yml; confirm `prisma_access/_runtime/api_client.py` has the `models = None` class default + `getattr(self.models, klass)`, the per-sub runtime files are gone, and `import prisma_access` succeeds. If the real OAG shape exposed a libcst-pass gap, add a fixture case in P1.2 and fix `runtime.py` (TDD), don't patch the artifact.
- [ ] **Step 3: Confirm the divergent-scheme bearer** — objects (`scmToken`) vs ztna (`bearerAuth`): assert the transport hook attaches the bearer regardless of each op's `_auth_settings` (a unit assertion on a generated `*_api.py` that `_auth_settings` differs across subs, plus the `_BearerApiClient` ignores it).
- [ ] **Step 4: Run live (if creds)** — `uv run nox -s live` (skips without `.env`); confirm a real CRUD call on one sub-package authenticates and the base-path is correct (F4 silent-404 check). **rev-2 S3:** check base-path for all three first-light subs, not just one.
- [ ] **Step 5: Commit** — `git commit -m "test(sdk): first-light verification (per-handle models, shared pool, transport bearer)"`

**P1 done when:** the 3 sub-packages build, hoist to one `_runtime`, share one auth/pool, and a real response deserializes into the right namespace; `nox -s gate` green; single-spec products still build.

---

# Milestone P2 — Full federation (composer + `_SUBPACKAGES`)

*Goal: all 12 sub-packages, one composing `Client`, the `_SUBPACKAGES` registry, per-sub smoke, one distribution scaffold.*

### Task P2.1: Composer template + render step

**Files:**
- Create: `src/phantasos/generator/sdk/components/facade/composer.py.jinja`
- Modify: `src/phantasos/generator/sdk/build.py` (render composer LAST, after hoist + auth + all subs)
- Test: `tests/test_render.py` (offline render assertion) + `tests/test_sdk_build.py` (slow, full)

**Interfaces:**
- Produces: `prisma_access/__init__.py` exporting `Client` and `_SUBPACKAGES: dict[str, type]` (slug → sub-package facade `Client`). `Client.from_env()/from_credentials()` build one `SdkConfiguration` (via `_auth.configuration_from_env` — rev-2) → one `RESTClientObject`/pool → N `_BearerApiClient(cfg)` handles, each with `.models` set as an **instance attribute** (rev-2 B1, not a ctor arg) and `.rest_client = pool` → each injected into the sub-package facade `Client(api_client=...)`, exposed as `self.<slug>`. Applies `default_headers` per handle (P3.1).

- [ ] **Step 1: Write the failing test** (offline render)

```python
def test_composer_emits_client_and_subpackages_registry():
    from phantasos.generator.sdk import build as B
    txt = B._render_composer(["objects", "network_services", "ztna_connector"],
                             root_package="prisma_access",
                             config_class_name="SdkConfiguration")
    assert "_SUBPACKAGES = {" in txt
    assert '"objects":' in txt
    assert "class Client" in txt
    assert "self.objects =" in txt
    assert "rest_client" in txt           # shared pool wiring
```

- [ ] **Step 2: Run → fail** — FAIL.

- [ ] **Step 3: Implement the template** `composer.py.jinja` (rendered with `slugs`, `root_package`, `config_class_name`):

```jinja
"""Top-level composing client for {{ root_package }} (written by phantasos)."""
from __future__ import annotations
{% for slug in slugs %}import {{ root_package }}.{{ slug }}.models as _{{ slug }}_models
from {{ root_package }}.{{ slug }}.extras.facade import Client as _{{ slug }}_Client
{% endfor %}
from {{ root_package }}._runtime.rest import RESTClientObject
from {{ root_package }}._auth import (
    {{ config_class_name }}, _BearerApiClient,
    configuration_from_env as _configuration_from_env,
    configuration_from_credentials as _configuration_from_credentials,
)

_SUBPACKAGES = {
{% for slug in slugs %}    "{{ slug }}": _{{ slug }}_Client,
{% endfor %}}
_HANDLE_MODELS = {
{% for slug in slugs %}    "{{ slug }}": _{{ slug }}_models,
{% endfor %}}
__all__ = ["Client", "_SUBPACKAGES"]


class Client:
    def __init__(self, configuration: {{ config_class_name }}):
        pool = RESTClientObject(configuration)
{% for slug in slugs %}        _ac_{{ slug }} = _BearerApiClient(configuration)
        _ac_{{ slug }}.models = _{{ slug }}_models          # rev-2 B1: instance attr, not ctor arg
        _ac_{{ slug }}.rest_client = pool                   # one shared pool
        self.{{ slug }} = _{{ slug }}_Client(_ac_{{ slug }})
{% endfor %}        self._configuration = configuration

    @classmethod
    def from_env(cls, **kwargs) -> "Client":
        return cls(_configuration_from_env(**kwargs))

    @classmethod
    def from_credentials(cls, **kwargs) -> "Client":
        return cls(_configuration_from_credentials(**kwargs))
```

Add `build._render_composer(...)` (direct Jinja render of `facade/composer.py.jinja`) and call it to write `project_dir/prisma_access/__init__.py` **last** (after hoist + auth, before scaffold) so it overwrites OAG's empty parent `__init__`. `default_headers` wiring (P3.1) is added to `__init__` (set on each `_ac_<slug>.default_headers`).

- [ ] **Step 4: Run → pass** — offline render test PASS; then the full 12-sub slow build test (P2.2) exercises it end-to-end.

- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): composer (__init__) — one Client, one pool, _SUBPACKAGES registry"`

### Task P2.2: All 12 sub-packages + provenance + pyproject

**Files:**
- Modify: `products/prisma-access/sdk.yml` (all 12 subpackages + `project:` + `default_headers` placeholder)
- Modify: `src/phantasos/generator/sdk/build.py:106-113` (`_about` per-sub or one manifest; fix `phantasos_version="0.1.0"` → `importlib.metadata.version("phantasos")`)
- Verify: `src/phantasos/scaffold/pyproject.toml.jinja:28` `packages = ["prisma_access"]` includes the whole tree (hatchling) — no change expected
- Test: `tests/test_sdk_build.py` (slow, all 12) + `tests/test_sdk_build.py` provenance assertion

**Interfaces:** consumes the composer (P2.1) + hoist (P1.2) + auth (P1.3).

- [ ] **Step 1: Write the failing tests** — (a) provenance: `_about.py` has a real phantasos version, not `0.1.0`; (b) slow full build: `import prisma_access` exposes all 12 `.<slug>` attrs and `_SUBPACKAGES` has 12 keys.

```python
def test_about_uses_real_phantasos_version(tmp_path, monkeypatch):
    from phantasos.generator.sdk.build import _about_text   # extracted helper
    txt = _about_text(spec_version="1.0", oag_version="7.22.0")
    assert '"0.1.0"' not in txt and "PHANTASOS_VERSION" in txt
```

- [ ] **Step 2: Run → fail** — FAIL.
- [ ] **Step 3: Implement.** Replace the hardcoded `phantasos_version="0.1.0"` with `importlib.metadata.version("phantasos")` (guard `PackageNotFoundError` → `"0+unknown"`). Author the full `products/prisma-access/sdk.yml` (all 12 subs per spec §7) + `overrides/README.md.jinja`. Confirm the wheel-packaging line.
- [ ] **Step 4: Run → pass** — provenance test PASS; full slow build → `import prisma_access` works, 12 sub-packages present, `len(prisma_access._SUBPACKAGES) == 12`.
- [ ] **Step 5: Commit** — `git commit -m "feat(prisma-access): all 12 sub-packages + real provenance version"`

### Task P2.3: Smoke counts the federated tree

> **Rev-2 (over-build cut):** `_import_walk` already `walk_packages(import_module("prisma_access").__path__, "prisma_access.")` — it recurses **all** 12 subs + `_runtime` + `_auth` in one pass. **No `subpackages` param** is threaded. Only `_count_operations` needs fixing (its `glob(project_dir/package/"api")` misses the nested layout).

**Files:**
- Modify: `src/phantasos/generator/sdk/smoke.py:33-41` (`_count_operations` → recursive glob)
- Test: `tests/test_smoke.py`

**Interfaces:** `smoke(project_dir, package, run=)` unchanged. `_count_operations` becomes layout-agnostic.

- [ ] **Step 1: Write the failing test** — `_count_operations` over a synthetic `prisma_access/objects/api/x_api.py` + `prisma_access/posture/api/y_api.py` returns the summed count; a single-spec `pkg/api/z_api.py` still works; the root (no top-level `api/`) returns the nested total without error.
- [ ] **Step 2: Run → fail** — FAIL (today's `Path(project_dir)/package/"api"` glob misses the nested `api/`).
- [ ] **Step 3: Implement** — change the glob to `Path(project_dir).joinpath(*package.split(".")).rglob("*_api.py")` (one recursive glob; works for single-spec AND federated). Leave `_import_walk` untouched.
- [ ] **Step 4: Run → pass** — PASS; full build `run_smoke=True` reports `failed == 0` and a non-zero op count across all 12.
- [ ] **Step 5: Commit** — `git commit -m "feat(sdk): layout-agnostic operation count (federated tree)"`

**P2 done when:** `import prisma_access; Client.from_env()` exposes all 12 over one Config/pool/token; `_SUBPACKAGES` has 12 entries; smoke `failed == 0`; composer overwrote the empty parent cleanly.

---

# Milestone P3 — Surface polish (classification, anchoring, headers)

### Task P3.1: Per-sub classification/anchoring + region/tenant default headers

> **Rev-2 (B6 + decision 2):** headers go on **`ApiClient.default_headers`** (the handle), NOT `Configuration` — OAG reads `self.default_headers` (`api_client.py:89,183`); setting it on `Configuration` sends nothing. Keep `required_for` fail-loud.

**Files:**
- Modify: `products/prisma-access/sdk.yml` (per-sub `operations:` for the 3 anchorless PUTs + non-CRUD ops; ztna `normalize_operation_ids` already set; verb-vocab is engine-side and already reusable; `default_headers:` block)
- Modify: `src/phantasos/productconfig.py` (`default_headers` config model + context wiring)
- Modify: `src/phantasos/generator/sdk/components/facade/composer.py.jinja` (apply headers on each `_ac_<slug>.default_headers` from env; raise early if a `required_for` sub is built with its env unset)
- Test: `tests/test_sdk_wrapper.py` (anchoring), `tests/test_productconfig.py` (default_headers parse), `tests/test_render.py` (composer emits the header/required_for wiring), live header assertion

**Interfaces:** `ProductConfig.default_headers: dict[str, HeaderSpec]` where `HeaderSpec(env: str, required: bool = False, required_for: list[str] = [])`. The composer, in `Client.__init__`, sets `ac.default_headers[<header>] = os.environ[<env>]` per handle, and raises `RuntimeError` when a header with `required_for` includes the sub-package being built and its env is unset. Threaded into the composer render context (a `headers` list).

- [ ] **Step 1: Write the failing tests** — (a) a previously-anchorless op (a network-services PUT with no CRUD sibling) is reachable via an `operations:` override and classified; (b) `default_headers` with `required_for: [incidents]` parses; (c) the rendered composer contains the `default_headers` apply + the `required_for` guard for `incidents`; (d) (slow/live or a constructed-handle unit) `client.incidents` with `PANW_REGION` unset raises a clear `RuntimeError`.
- [ ] **Step 2: Run → fail** — FAIL.
- [ ] **Step 3: Implement** — add the `HeaderSpec` model + `default_headers` context wiring; author the `operations:` overrides per sub; in the composer template, after building each `_ac_<slug>`, set its `.default_headers` from env and enforce `required_for`. Verb-vocab needs no change.
- [ ] **Step 4: Run → pass** — PASS; `phantasos sdk build prisma-access` exposes the non-CRUD ops; a built `Client` sends `X-PANW-Region` on `incidents` calls (live) / raises when unset.
- [ ] **Step 5: Commit** — `git commit -m "feat(prisma-access): anchoring overrides + region/tenant headers on the handle"`

**P3 done when:** all 12 sub-packages classify cleanly (no anchorless-op build failure), region/tenant headers apply **on the ApiClient handle** with fail-loud required-ness, non-CRUD ops reachable.

---

# Milestone P4 — Docs federation + live

### Task P4.1: `_SUBPACKAGES`-driven `gen_ref_pages.py.jinja`

**Files:**
- Modify: `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` (loop `prisma_access._SUBPACKAGES`)
- Test: `tests/test_sdk_docs_emitted.py` / `tests/cli/test_docs_scaffold.py` (offline render of the script + a federated-tree assertion); `nox -s sdk-docs` (slow)

**Interfaces:** the script imports `{{ package }}` (= `prisma_access`), reads `_SUBPACKAGES`, and for each `<slug>` walks `prisma_access.<slug>.extras.facade._WRAPPERS` + `prisma_access.<slug>/models`, emitting pages under `reference/<slug>/…`.

- [ ] **Step 1: Write the failing test** — render `gen_ref_pages.py.jinja` for a federated `package=prisma_access`; assert the emitted script references `_SUBPACKAGES` and builds `reference/<slug>/...` paths (string-level), and that a single-spec product (no `_SUBPACKAGES`) still renders the legacy single-package loop.
- [ ] **Step 2: Run → fail** — FAIL.
- [ ] **Step 3: Implement** — branch the template on a `federated` flag (or detect `_SUBPACKAGES`): when federated, `for slug, _client in importlib.import_module(PACKAGE)._SUBPACKAGES.items(): facade = import_module(f"{PACKAGE}.{slug}.extras.facade"); src = Path(...)/PACKAGE/slug; ...` emitting under `reference/{slug}/...`. Keep the single-package branch byte-identical for legacy products.
- [ ] **Step 4: Run → pass** — render test PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(docs): federated gen_ref_pages loops _SUBPACKAGES"`

### Task P4.2: `build_docs_context` targets the showcase sub-package

**Files:**
- Modify: `src/phantasos/generator/sdk/docs.py:192-221` (`build_docs_context`)
- Test: `tests/test_sdk_docs_context.py`

**Interfaces:** when `cfg.docs.showcase_subpackage` is set, `build_docs_context` runs `cli_operations`/facade-validate/`models` import against `f"{cfg.package}.{cfg.docs.showcase_subpackage}"`; the showcase attr renders `client.<sub>.<object>`.

- [ ] **Step 1: Write the failing test** — with `showcase_subpackage="objects"`, `_wrapper_objects` and `cli_operations` are called with `"prisma_access.objects"`, not `"prisma_access"`; the showcase guide string is `client.objects.address`.
- [ ] **Step 2: Run → fail** — FAIL.
- [ ] **Step 3: Implement** — compute `showcase_pkg = f"{cfg.package}.{cfg.docs.showcase_subpackage}" if cfg.docs.showcase_subpackage else cfg.package` and thread it through `_validate_object`/`cli_operations`/`models_ns`. Site name defaults to the distribution.
- [ ] **Step 4: Run → pass** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(docs): build_docs_context targets showcase sub-package"`

### Task P4.3: prisma-access docs site + live CRUD + strict build

**Files:**
- Modify: `products/prisma-access/sdk.yml` (`docs:` block — `showcase_subpackage: objects`, `showcase_resource: address`, `site_name`)
- Modify: `nox.toml` (enroll `prisma-access` in `live` + `sdk-docs`)
- Test: `nox -s sdk-docs` (strict build + per-sub reference-page count assertion); `nox -s live`

**Interfaces:** consumes P4.1–P4.2 + the full build.

- [ ] **Step 1** — author the `docs:` block + enroll in `nox.toml`; add a `[[sdk-docs.assert]]` guard that the reference covers each sub-package (≥1 page per slug).
- [ ] **Step 2: Run docs** — `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pa NOX_ENVDIR=$HOME/.tmp/pa-nox uv run nox -s sdk-docs` → `mkdocs build --strict` passes; `site/reference/objects/…` etc. exist for all 12.
- [ ] **Step 3: Run live** — `uv run nox -s live` → CRUD passes where creds exist.
- [ ] **Step 4: Update context docs** — refresh `.agents/context/sdk-generator.md`, `product-config.md`, `scaffold.md` narratives; `uv run nox -s context -- --check` passes.
- [ ] **Step 5: Commit** — `git commit -m "feat(prisma-access): federated docs site + live/sdk-docs enrollment"`

**P4 / definition of done:** `prisma-access-sdk` builds all 12 sub-packages under `prisma_access`; `import prisma_access` + `Client.from_env()` works over one shared token/Config/pool; each sub-package smoke-imports clean; posture authenticates via the transport bearer; the opt-in docs site builds `--strict` with reference across all 12; live CRUD passes where creds exist; `CHANGELOG.md` `## [Unreleased]` updated; CLI out of scope (the `_SUBPACKAGES` seam is in place).

---

## Self-review notes (author checklist — done before handing to reviewers)

- **Spec coverage:** D2 (P1.1 loop), D2.0/skip-validate (P0.1), ExternalTags (P0.4), D3 namespacing (federated by construction — P1.1), D4 transport bearer (P1.3), D5 facade+composer (P2.1), D6 subpackages config (P0.2–0.3), D7 phasing (P0–P4), D8 runtime hoist (P1.2), D9 docs (P4), D10 `_SUBPACKAGES` (P2.1) + ztna normalize (P0.5). All mapped.
- **Review outcome (resolved — see the rev-2 block):** the two-Opus review (python-pro + ponytail) found 6 runtime blockers (B1–B6) + over-build; all folded in. The earlier "open confirmations" are now decided: (a) `vendor()` threads `package`/`context`/`distribution_root` (no clone); (b) the hoist is **libcst**, not regex, and does **not** touch `__init__` (B1); (c) `default_headers` keeps `required_for`, applied on the **ApiClient handle** (B6); (d) composer is a direct render (no model); (e) `_auth.configuration_from_env/_credentials` added (P1.3). The one taste call (Q4) — keep `NormalizeIds` explicit, drop the other three surfaces.
- **Risk hotspots (from spec §10, with rev-2 mitigations):** runtime-hoist completeness — the libcst pass covers `_runtime`+`api/`+`extras/` and the P1.2 test imports the whole tree from real-OAG-shaped fixtures (B1/B2/B3); base-path silent-404 — P1.4 live checks **all** first-light subs (S3); composer write-order (last — P2.1); per-sub auth-shim resolves the facade's `from .auth` (B4); docs reference completeness (strict + per-sub assert — P4.3).
