# Generated-SDK user documentation (mkdocs) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `phantasos sdk build` emit a complete, strictly-building Material for MkDocs site (Getting Started, Architecture, auth/pagination/CRUD guides, and an mkdocstrings API reference) into any SDK whose product opts in via a `docs:` block.

**Architecture:** A new config-gated docs stage in `generator/sdk/build.py` runs a scoped, in-process `introspect()` of the author-named showcase resource (right after the `vendor` step, where `facade._RESOURCES` exists), shapes a `docs_context`, and the existing `render_scaffold` emits gated `.jinja` doc templates. The reference is mkdocstrings autodoc; a generated MkDocs `hooks:` logging filter keeps `mkdocs build --strict` green against OAG's sphinx docstrings.

**Tech Stack:** Python 3.11+, pydantic v2, Jinja2 (StrictUndefined scaffold engine), nox/uv, Material for MkDocs + mkdocstrings[python]/griffe + mkdocs-gen-files + mkdocs-literate-nav.

**Spec:** `docs/specs/2026-06-17-sdk-generated-docs-design.md` (read it first; spikes resolved 2026-06-18).

---

## Pre-flight (read once)

- **Env for every `uv`/`nox` command** (sshfs-safe, per `CLAUDE.md`):
  `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-cli NOX_ENVDIR=/tmp/phantasos-nox`
- **Offline gate:** `uv run nox -s gate` (ruff + format + mypy + pytest). Run after each phase.
- **Reference SDK already built at** `/home/ubuntu/git/prisma-browser-sdk` (used by the integration gate). Rebuild with `uv run nox -s smoke` or `phantasos sdk build prisma-browser`.
- **Showcase resource for prisma-browser = `applications`.** Verified canonical ops the heuristic must resolve:
  - create → `create_application` (body `CreateOrReplaceAppInput`, required path `type`)
  - read   → `get_application_by_id` (required path `id`)
  - list   → `list_applications` (all-optional query; paginated)
  - update → `patch_application_by_type_and_id` (body `PatchAppInput`, required path `type`,`id`)
  - delete → `delete_application_by_id` (required path `id`)
- **Commit style:** Conventional Commits, scope `cli`/`sdk`/`docs`. Never bump `version` on this branch. Record user-facing change under `## [Unreleased]` in `CHANGELOG.md`.
- **Branch:** work on `feature/sdk-generated-docs` (already cut from `develop`). If starting fresh: `git checkout develop && git pull && git checkout -b feature/sdk-generated-docs`.
- **Gating idiom (load-bearing):** every gated template uses `{% if has_docs | default(false) %}`, never bare `{% if has_docs %}`. The scaffold engine uses `StrictUndefined`, so a bare reference raises `UndefinedError` whenever a render context omits `has_docs` (existing `tests/test_scaffold.py` contexts do). Verified empirically.
- **Reviewed & re-spiked (2026-06-18):** three expert reviews + a full-tree (`14 api + 401 models`) strict-build spike validated the mkdocs config below; see spec §11 "Spike round 2".

## File structure

**New:**
- `src/phantasos/generator/sdk/docs.py` — scoped introspect + verb classification + `build_docs_context`.
- `src/phantasos/scaffold/docs/index.md.jinja` — Home.
- `src/phantasos/scaffold/docs/getting-started.md.jinja` — quickstart tutorial.
- `src/phantasos/scaffold/docs/architecture.md.jinja` — concepts + Mermaid.
- `src/phantasos/scaffold/docs/guides/authentication.md.jinja`
- `src/phantasos/scaffold/docs/guides/pagination.md.jinja`
- `src/phantasos/scaffold/docs/guides/crud.md.jinja`
- `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` — gen-files reference generator.
- `src/phantasos/scaffold/docs/_hooks.py.jinja` — strict-build logging filter.
- `tests/test_cli_docs.py` — offline classification + context-shaping tests.
- `tests/test_sdk_docs_emitted.py` — offline scaffold-emission tests.

**Modified:**
- `src/phantasos/productconfig.py` — `DocsOperations`, `DocsConfig`, `ProductConfig.docs`, `has_docs` in context + `_AUTO_EXPOSED`.
- `src/phantasos/generator/sdk/build.py` — docs stage + context merge.
- `src/phantasos/scaffold/mkdocs.yml.jinja` — gate on `has_docs`; nav, plugins, `docstring_style: sphinx`, filters, `hooks`, Mermaid.
- `src/phantasos/scaffold/pyproject.toml.jinja` — gated `docs` dependency group.
- `src/phantasos/scaffold/noxfile.py.jinja` — gated `docs` + `docs_serve` sessions.
- `src/phantasos/scaffold/.github/workflows/docs.yml.jinja` — gate on `has_docs`; install `docs` group.
- `products/prisma-browser/sdk.yml` — add `docs:` block.
- `noxfile.py` — new `docs` integration session.
- `.agents/context/sdk-generator.md` — document the docs stage; then `uv run nox -s context`.
- `CHANGELOG.md` — `## [Unreleased]` entry.

---

## Phase 1 — Config surface

### Task 1: `DocsConfig` / `DocsOperations` models + `ProductConfig.docs`

**Files:**
- Modify: `src/phantasos/productconfig.py`
- Test: `tests/test_productconfig.py` (create if absent)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_productconfig.py
from phantasos.productconfig import DocsConfig, DocsOperations, ProductConfig


def test_docs_config_defaults():
    d = DocsConfig(showcase_resource="applications")
    assert d.showcase_resource == "applications"
    assert d.site_name is None
    assert d.operations is None


def test_docs_operations_override_parsed():
    d = DocsConfig(
        showcase_resource="applications",
        operations={"create": "create_application", "read": "get_application_by_id"},
    )
    assert d.operations.create == "create_application"
    assert d.operations.read == "get_application_by_id"
    assert d.operations.list is None


def test_product_config_docs_absent_is_none():
    cfg = ProductConfig(package="p", output="o", base_url="https://x")
    assert cfg.docs is None


def test_product_config_docs_present():
    cfg = ProductConfig(
        package="p", output="o", base_url="https://x",
        docs={"showcase_resource": "applications"},
    )
    assert cfg.docs.showcase_resource == "applications"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-cli; uv run pytest tests/test_productconfig.py -q`
Expected: FAIL — `ImportError: cannot import name 'DocsConfig'`.

- [ ] **Step 3: Add the models and wire `docs` into `ProductConfig`**

In `src/phantasos/productconfig.py`, add after `ProjectConfig` (around line 39):

```python
class DocsOperations(BaseModel):
    """Optional per-verb override of the showcase resource's CRUD methods."""

    model_config = ConfigDict(extra="forbid")
    create: str | None = None
    read: str | None = None
    list: str | None = None
    update: str | None = None
    delete: str | None = None


class DocsConfig(BaseModel):
    """Opt-in user-documentation generation (sdk.yml `docs:` block)."""

    model_config = ConfigDict(extra="forbid")
    showcase_resource: str
    site_name: str | None = None
    operations: DocsOperations | None = None
```

In `ProductConfig`, add a field (next to `project`):

```python
    docs: DocsConfig | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_productconfig.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(sdk): add docs: product-config block (DocsConfig/DocsOperations)"
```

### Task 2: Expose `has_docs` to the Jinja context

**Files:**
- Modify: `src/phantasos/productconfig.py` (the `context` dict in `load_product`, ~line 203; `_AUTO_EXPOSED`, ~line 141)
- Test: `tests/test_productconfig.py`

- [ ] **Step 1: Write the failing test**

```python
def test_has_docs_in_context(tmp_path):
    # Minimal product dir: sdk.yml + empty openapi.yml
    import textwrap
    (tmp_path / "openapi.yml").write_text("info: {title: T, version: '1'}\n")
    (tmp_path / "sdk.yml").write_text(textwrap.dedent("""
        package: p
        output: ./out
        base_url: https://x
        docs: {showcase_resource: applications}
        project: {distribution: p, author: A, author_email: a@b.c, repo_url: https://h/p}
    """))
    from phantasos.productconfig import load_product
    loaded = load_product(str(tmp_path / "sdk.yml"))
    assert loaded.context["has_docs"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_productconfig.py::test_has_docs_in_context -q`
Expected: FAIL — `KeyError: 'has_docs'`.

- [ ] **Step 3: Add `has_docs` to context + `_AUTO_EXPOSED`**

In `_AUTO_EXPOSED` (the set near line 141) add `"has_docs",`.

In the `context` dict built in `load_product` (near line 213, alongside `has_retry`), add:

```python
        "has_docs": cfg.docs is not None,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_productconfig.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(sdk): expose has_docs to the scaffold context"
```

---

## Phase 2 — Verb classification + context shaping (`generator/sdk/docs.py`)

This phase is pure, offline-testable logic. `build_docs_context` (the introspect wrapper) is thin; everything testable takes an `OperationInventory` as input data (NOT a mock of the SUT).

### Task 3: Verb classification heuristic

**Files:**
- Create: `src/phantasos/generator/sdk/docs.py`
- Test: `tests/test_cli_docs.py`

- [ ] **Step 1: Write the failing test** (data mirrors the real `applications` surface)

```python
# tests/test_cli_docs.py
from phantasos.generator.cli.inventory import OperationInfo, ParamInfo
from phantasos.generator.sdk.docs import classify_operations


def _op(method, params):
    return OperationInfo(
        resource="applications", method=method,
        params=[ParamInfo(**p) for p in params],
    )


def _path(name, required=True):
    return {"name": name, "annotation": "str", "location": "path", "required": required}


def _body(name, model):
    return {"name": name, "annotation": model, "location": "body",
            "required": True, "body_model": model}


APPLICATIONS = [
    _op("bulk_create_applications", [_path("type")]),
    _op("create_application", [_path("type"), _body("create_or_replace_app_input", "CreateOrReplaceAppInput")]),
    _op("get_application_by_id", [_path("id")]),
    _op("get_application_by_type_and_id", [_path("type"), _path("id")]),
    _op("list_applications", []),
    _op("list_applications_by_type", [_path("type")]),
    _op("list_application_categories", []),
    _op("patch_application_by_type_and_id", [_path("type"), _path("id"), _body("patch_app_input", "PatchAppInput")]),
    _op("delete_application_by_id", [_path("id")]),
    _op("delete_application_by_type_and_id", [_path("type"), _path("id")]),
    _op("bulk_delete_applications", []),
]


def test_classify_picks_canonical_ops():
    slots = classify_operations(APPLICATIONS, "applications", None)
    assert slots["create"].method == "create_application"
    assert slots["read"].method == "get_application_by_id"
    assert slots["list"].method == "list_applications"
    assert slots["update"].method == "patch_application_by_type_and_id"
    assert slots["delete"].method == "delete_application_by_id"


def test_classify_rejects_different_noun():
    slots = classify_operations(APPLICATIONS, "applications", None)
    # list_application_categories is a different noun -> never chosen for "list"
    assert slots["list"].method != "list_application_categories"


def test_classify_excludes_bulk():
    slots = classify_operations(APPLICATIONS, "applications", None)
    assert not slots["create"].method.startswith("bulk_")


def test_classify_partial_crud_omits_missing(monkeypatch):
    ops = [_op("create_application", [_path("type"), _body("b", "B")]),
           _op("list_applications", [])]
    slots = classify_operations(ops, "applications", None)
    assert set(slots) == {"create", "list"}


def test_classify_honours_override():
    from phantasos.productconfig import DocsOperations
    ov = DocsOperations(read="get_application_by_type_and_id")
    slots = classify_operations(APPLICATIONS, "applications", ov)
    assert slots["read"].method == "get_application_by_type_and_id"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_docs.py -q`
Expected: FAIL — `ModuleNotFoundError: ...generator.sdk.docs`.

- [ ] **Step 3: Implement `classify_operations`**

```python
# src/phantasos/generator/sdk/docs.py
"""Scoped introspect + verb classification + docs context for generated SDKs."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from ...productconfig import DocsOperations, LoadedProduct
    from ..cli.inventory import OperationInfo, OperationInventory

# Leading method token -> CRUD slot. "patch"/"put" also mean update.
_VERB_SLOT = {
    "create": "create", "get": "read", "list": "list",
    "update": "update", "patch": "update", "put": "update", "delete": "delete",
}
_BY_SUFFIX = re.compile(r"_by_.*$")


def _slot(method: str) -> str | None:
    return _VERB_SLOT.get(method.split("_", 1)[0])


def _noun(method: str) -> str:
    """Method minus its verb prefix and any `_by_<...>` suffix."""
    rest = method.split("_", 1)[1] if "_" in method else ""
    return _BY_SUFFIX.sub("", rest)


def _matches_resource(resource: str, noun: str) -> bool:
    r, n = resource.rstrip("s"), noun.rstrip("s")
    return r == n or resource == noun or resource.startswith(noun)


def _required_path_count(op: OperationInfo) -> int:
    return sum(1 for p in op.params if p.location == "path" and p.required)


def classify_operations(
    operations: list[OperationInfo], resource: str, overrides: DocsOperations | None
) -> dict[str, OperationInfo]:
    """Map each CRUD slot to its canonical OperationInfo (present slots only)."""
    by_method = {op.method: op for op in operations}
    override_map = (
        {k: v for k, v in vars(overrides).items() if v} if overrides else {}
    )

    slots: dict[str, OperationInfo] = {}
    for slot in ("create", "read", "list", "update", "delete"):
        pinned = override_map.get(slot)
        if pinned and pinned in by_method:
            slots[slot] = by_method[pinned]
            continue
        candidates = [
            op for op in operations
            if _slot(op.method) == slot
            and not op.method.startswith("bulk_")
            and _matches_resource(resource, _noun(op.method))
        ]
        if candidates:
            slots[slot] = min(
                candidates, key=lambda op: (_required_path_count(op), len(op.method))
            )
    return slots
```

> **Heuristic caveat:** the `(required_path_count, len(method))` tie-break is a
> heuristic, verified correct against all 11 real `ApplicationsApi` methods but
> not guaranteed for every resource/product. The `docs.operations` override
> (Task 1) is the documented escape hatch when it mis-picks.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_docs.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/sdk/docs.py tests/test_cli_docs.py
git commit -m "feat(sdk): canonical CRUD verb classification for docs guides"
```

### Task 4: Context shaping (`_shape_context`)

Turns the classified slots + components into a plain-dict `docs_context` the Jinja templates consume. Plain dicts (not pydantic) so templates use `op.method` style attribute access via Jinja's dict lookup.

**Files:**
- Modify: `src/phantasos/generator/sdk/docs.py`
- Test: `tests/test_cli_docs.py`

- [ ] **Step 1: Write the failing test**

```python
def test_shape_context_shapes_showcase_and_credentials():
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.inventory import OperationInventory
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(
        sdk_package="prisma_browser", sdk_version="1.0.0", operations=APPLICATIONS
    )
    ctx = shape_context(
        inv, resource="applications", site_name="Demo",
        auth=ScmOAuth(type="scm_oauth"), overrides=None, has_pagination=True,
    )
    assert ctx["has_docs"] is True
    assert ctx["site_name"] == "Demo"
    sc = ctx["showcase"]
    assert sc["attr"] == "applications"
    assert sc["has_create"] and sc["has_list"]
    assert sc["operations"]["create"]["method"] == "create_application"
    # create requires the `type` path arg + the body model
    create_args = sc["operations"]["create"]["required_args"]
    assert any(a["name"] == "type" and a["kind"] == "path" for a in create_args)
    assert any(a["kind"] == "body" and a["body_model"] == "CreateOrReplaceAppInput"
               for a in create_args)
    # credentials come from the auth descriptor
    names = {c["env_var"] for c in ctx["credentials"]}
    assert {"CLIENT_ID", "CLIENT_SECRET", "SCOPE"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_docs.py::test_shape_context_shapes_showcase_and_credentials -q`
Expected: FAIL — `ImportError: cannot import name 'shape_context'`.

- [ ] **Step 3: Implement `shape_context`**

Append to `src/phantasos/generator/sdk/docs.py`:

```python
def _op_dict(op: OperationInfo) -> dict[str, object]:
    required_args: list[dict[str, object]] = []
    for p in op.params:
        if not p.required:
            continue
        if p.location == "body":
            required_args.append({
                "name": p.name, "kind": "body", "body_model": p.body_model,
            })
        elif p.location == "path":
            placeholder = (p.enum_values[0] if p.enum_values else f"<{p.name}>")
            required_args.append({
                "name": p.name, "kind": "path", "placeholder": str(placeholder),
            })
    return {
        "method": op.method,
        "summary": op.summary,
        "description": op.description,
        "required_args": required_args,
        "return_model": op.return_model,
        "items_field": op.items_field,
    }


def shape_context(
    inventory: OperationInventory, *, resource: str, site_name: str,
    auth: object | None, overrides: DocsOperations | None, has_pagination: bool,
) -> dict[str, object]:
    ops = [op for op in inventory.operations if op.resource == resource]
    slots = classify_operations(ops, resource, overrides)
    operations = {slot: _op_dict(op) for slot, op in slots.items()}
    showcase = {
        "attr": resource,
        "operations": operations,
        "has_create": "create" in operations,
        "has_read": "read" in operations,
        "has_list": "list" in operations,
        "has_update": "update" in operations,
        "has_delete": "delete" in operations,
        "list": operations.get("list"),
    }
    credentials = []
    if auth is not None and hasattr(auth, "credential_fields"):
        for f in auth.credential_fields():
            credentials.append({
                "name": f.name, "env_var": f.env_var,
                "secret": f.secret, "required": f.required,
            })
    return {
        "has_docs": True,
        "site_name": site_name,
        "showcase": showcase,
        "credentials": credentials,
        "show_pagination_guide": has_pagination and showcase["has_list"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_docs.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/sdk/docs.py tests/test_cli_docs.py
git commit -m "feat(sdk): shape docs context (showcase ops + credentials)"
```

### Task 5: `build_docs_context` (introspect wrapper + validation)

**Files:**
- Modify: `src/phantasos/generator/sdk/docs.py`
- Test: integration-covered by Phase 7's `nox -s sdk-docs`; add a focused error-path unit test here.

- [ ] **Step 1: Write the failing test** (unknown showcase resource fails fast)

```python
def test_build_docs_context_unknown_resource(tmp_path):
    import pytest
    from phantasos.generator.cli.inventory import OperationInventory
    from phantasos.generator.sdk import docs

    inv = OperationInventory(sdk_package="p", sdk_version="1", operations=APPLICATIONS)
    with pytest.raises(ValueError, match="nope.*applications"):
        docs._validate_resource(inv, "nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_docs.py::test_build_docs_context_unknown_resource -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_validate_resource'`.

- [ ] **Step 3: Implement the wrapper + validation**

Append to `src/phantasos/generator/sdk/docs.py`:

```python
def _validate_resource(inventory: OperationInventory, resource: str) -> None:
    available = sorted({op.resource for op in inventory.operations})
    if resource not in available:
        raise ValueError(
            f"docs.showcase_resource {resource!r} not found; "
            f"available resources: {available}"
        )


def build_docs_context(loaded: LoadedProduct, project_dir: Path) -> dict[str, object]:
    """Scoped introspect of the showcase resource -> docs context dict."""
    from ..cli.introspect import introspect

    cfg = loaded.config
    assert cfg.docs is not None  # guarded by the caller
    inventory = introspect(cfg.package, project_dir)
    _validate_resource(inventory, cfg.docs.showcase_resource)
    site_name = cfg.docs.site_name or loaded.context.get("distribution", cfg.package)
    return shape_context(
        inventory,
        resource=cfg.docs.showcase_resource,
        site_name=str(site_name),
        auth=loaded.auth,
        overrides=cfg.docs.operations,
        has_pagination=bool(loaded.context.get("has_pagination")),
    )
```

**No new runtime imports are needed.** Because `docs.py` begins with
`from __future__ import annotations`, every type-only reference is a string at
runtime, so `OperationInventory`, `LoadedProduct`, `DocsOperations`, and `Path`
all stay under `TYPE_CHECKING`; `introspect` is imported locally inside
`build_docs_context` (shown above). The module's final import block is exactly:

```python
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from ...productconfig import DocsOperations, LoadedProduct
    from ..cli.inventory import OperationInfo, OperationInventory
```

(Adjust Task 3's skeleton header to match this — move `OperationInfo` under
`TYPE_CHECKING`. Do NOT add `# noqa: E402`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_docs.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/sdk/docs.py tests/test_cli_docs.py
git commit -m "feat(sdk): build_docs_context with fail-fast resource validation"
```

---

## Phase 3 — Build wiring

### Task 6: Run the docs stage in `build.build()`

**Files:**
- Modify: `src/phantasos/generator/sdk/build.py` (the scaffold call, lines 91-99)
- Test: covered by Phase 7 integration gate (in-process introspect needs a built SDK). No new offline test.

- [ ] **Step 1: Modify the scaffold render to merge docs context**

Replace the scaffold block (currently lines 91-99) with:

```python
    from ... import scaffold
    from . import docs as docs_stage

    overrides = loaded.base_dir / "overrides"
    context = dict(loaded.context)
    if loaded.config.docs is not None:
        context.update(docs_stage.build_docs_context(loaded, project_dir))
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        overrides if overrides.is_dir() else None,
        project_dir,
        context,
    )
```

- [ ] **Step 2: Smoke-verify the wiring compiles**

Run: `uv run python -c "import phantasos.generator.sdk.build"`
Expected: no output, exit 0.

- [ ] **Step 3: Run the offline gate**

Run: `uv run nox -s gate`
Expected: PASS (ruff/format/mypy/pytest all green).

> **Verification honesty:** the offline gate proves this compiles and type-checks
> but does NOT execute the new `cfg.docs` branch (that needs a real OAG build).
> The behavioral verification of this wiring is the **Task 13 integration gate**
> — treat Task 6 as not fully verified until Task 13 is green.

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/generator/sdk/build.py
git commit -m "feat(sdk): run the config-gated docs stage during sdk build"
```

---

## Phase 4 — Documentation templates

All templates are gated `{% if has_docs | default(false) %}...{% endif %}`; when `has_docs` is false the render is whitespace-only and `render_scaffold` skips the file (`scaffold.py:55`). Because the engine uses `StrictUndefined`, the `{% if has_docs | default(false) %}` guard MUST wrap every reference to `showcase`/`credentials`/`site_name`.

### Task 7: Strict-build logging hook + Home + Getting Started

**Files:**
- Create: `src/phantasos/scaffold/docs/_hooks.py.jinja`
- Create: `src/phantasos/scaffold/docs/index.md.jinja`
- Create: `src/phantasos/scaffold/docs/getting-started.md.jinja`

- [ ] **Step 1: Write `_hooks.py.jinja`** (verified in spike 3)

```jinja
{% if has_docs | default(false) %}"""MkDocs hook: silence griffe's benign duplicate-parameter warnings.

OpenAPI Generator documents each parameter in BOTH the sphinx docstring and the
`Annotated[..., Field(description=...)]` annotation; griffe flags the overlap as
'Duplicate parameter information'. It is cosmetic, but `--strict` aborts on any
WARNING. Drop just those records so strict still catches real problems.
"""

from __future__ import annotations

import logging

_NEEDLE = "Duplicate parameter information"


class _DropDuplicateParam(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return _NEEDLE not in record.getMessage()


_FILTER = _DropDuplicateParam()


def on_startup(**_kwargs: object) -> None:
    names = set(logging.root.manager.loggerDict) | {
        "griffe", "mkdocs.plugins.griffe", "mkdocs.plugins.mkdocstrings",
    }
    for name in names:
        if "griffe" in name or "mkdocstrings" in name:
            logging.getLogger(name).addFilter(_FILTER)
    for handler in logging.root.handlers:
        handler.addFilter(_FILTER)
{% endif %}
```

- [ ] **Step 2: Write `index.md.jinja`**

```jinja
{% if has_docs | default(false) %}# {{ site_name }}

{{ description }}

`{{ distribution }}` is the Python SDK for {{ spec_title or distribution }}. It wraps
every API resource in typed, idiomatic methods and handles authentication{% if has_pagination %}, pagination{% endif %}{% if has_retry %}, and retries{% endif %} for you.

```bash
pip install {{ distribution }}
```

```python
from {{ package }}.extras.facade import Client

client = Client.from_env()
```

## Where to go next

- **[Getting Started](getting-started.md)** — install, authenticate, make your first call.
- **[Architecture](architecture.md)** — how the client, resources, and components fit together.
{% if has_auth %}- **[Authentication](guides/authentication.md)** — credentials and configuration.
{% endif %}{% if show_pagination_guide %}- **[Pagination](guides/pagination.md)** — iterate large result sets.
{% endif %}- **[CRUD operations](guides/crud.md)** — create, read, update, and delete resources.
- **[API Reference](reference/)** — every resource, operation, and model.
{% endif %}
```

- [ ] **Step 3: Write `getting-started.md.jinja`** (auth-first; first real call uses the showcase resource)

```jinja
{% if has_docs | default(false) %}# Getting Started

This guide takes you from zero to your first successful API call.

## Install

```bash
pip install {{ distribution }}
```

{% if has_auth %}## Configure credentials

The client reads credentials from the environment. Set:

```bash
{% for c in credentials %}{% if c.required %}export {{ c.env_var }}="{% if c.secret %}…{% else %}your-{{ c.name }}{% endif %}"
{% endif %}{% endfor %}```

See the [Authentication guide](guides/authentication.md) for every option and for passing
credentials explicitly.
{% endif %}

## Your first call

```python
from {{ package }}.extras.facade import Client

client = Client.from_env()
{% if showcase.has_list %}
# List {{ showcase.attr }}
page = client.{{ showcase.attr }}.{{ showcase.operations["list"].method }}()
print(page){% elif showcase.has_read %}
result = client.{{ showcase.attr }}.{{ showcase.operations["read"].method }}({% for a in showcase.operations["read"].required_args %}{{ a.name }}="{{ a.placeholder }}"{% if not loop.last %}, {% endif %}{% endfor %})
print(result){% endif %}
```

You're set — continue to [CRUD operations](guides/crud.md).
{% endif %}
```

- [ ] **Step 4: Sanity-render the templates offline** (defer full assertions to Task 12)

Run: `uv run python -c "import phantasos.scaffold as s; print(s.builtin_dir())"`
Expected: prints the scaffold dir path (templates are picked up by directory walk).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/scaffold/docs/_hooks.py.jinja src/phantasos/scaffold/docs/index.md.jinja src/phantasos/scaffold/docs/getting-started.md.jinja
git commit -m "feat(sdk): emit docs hook, Home, and Getting Started pages"
```

### Task 8: Architecture page (descriptors + Mermaid)

**Files:**
- Create: `src/phantasos/scaffold/docs/architecture.md.jinja`

- [ ] **Step 1: Write `architecture.md.jinja`**

```jinja
{% if has_docs | default(false) %}# Architecture

`{{ distribution }}` is a thin, typed layer over the {{ spec_title or distribution }} REST API.

## The client

`Client.from_env()` builds one authenticated client. **Reuse a single client** across
requests — the first call mints an auth token that is then reused, so creating a client
per request is wasteful.

```mermaid
graph TD
    ENV[Environment / credentials] --> C[Client.from_env]
    C --> R[Resource APIs<br/>client.&lt;resource&gt;]
    R --> OP[Typed operations]
    OP --> H[urllib3 transport]
    H --> API[{{ spec_title or "REST API" }}]
```

## Components

This SDK is assembled from these components:

| Component | Role |
|-----------|------|
| Resource facade | `client.<resource>.<operation>(...)` — every API resource as an attribute |
{% if has_auth %}| Authentication | Injects credentials and refreshes the access token automatically |
{% endif %}{% if has_pagination %}| Pagination | `client.paginate(list_method, **filters)` iterates cursor pages |
{% endif %}{% if has_retry %}| Retry | Automatic retries with jittered backoff on transient failures |
{% endif %}{% if has_errors %}| Errors | Normalised error messages extracted from API error bodies |
{% endif %}

## Resources and operations

Each resource is a typed `*Api` class exposed as `client.<resource>`. Browse the full
surface in the **[API Reference](reference/)**.
{% endif %}
```

- [ ] **Step 2: Commit**

```bash
git add src/phantasos/scaffold/docs/architecture.md.jinja
git commit -m "feat(sdk): emit descriptor-driven Architecture page with Mermaid"
```

### Task 9: Guides — authentication, pagination, CRUD

**Files:**
- Create: `src/phantasos/scaffold/docs/guides/authentication.md.jinja`
- Create: `src/phantasos/scaffold/docs/guides/pagination.md.jinja`
- Create: `src/phantasos/scaffold/docs/guides/crud.md.jinja`

- [ ] **Step 1: Write `guides/authentication.md.jinja`**

```jinja
{% if has_docs | default(false) and has_auth %}# Authentication

`{{ distribution }}` authenticates with credentials supplied via the environment or
passed explicitly.

## Required credentials

| Variable | Required | Secret |
|----------|----------|--------|
{% for c in credentials %}| `{{ c.env_var }}` | {{ "yes" if c.required else "no" }} | {{ "yes" if c.secret else "no" }} |
{% endfor %}

## From the environment

```python
from {{ package }}.extras.facade import Client

client = Client.from_env()
```

## Passing credentials explicitly

```python
from {{ package }}.extras.facade import Client

client = Client.from_credentials(
{% for c in credentials %}{% if c.required %}    {{ c.name }}="…",
{% endif %}{% endfor %})
```

Store secrets in a secrets manager or environment variables — never hard-code them.
{% endif %}
```

- [ ] **Step 2: Write `guides/pagination.md.jinja`**

```jinja
{% if has_docs | default(false) and show_pagination_guide %}# Pagination

List endpoints return one page at a time. `client.paginate(...)` transparently follows
the cursor so you can iterate every item.

```python
from {{ package }}.extras.facade import Client

client = Client.from_env()

for item in client.paginate(client.{{ showcase.attr }}.{{ showcase.operations["list"].method }}):
    print(item)
```

`paginate` yields items across all pages; the server decides the page size. To cap the
work, break out of the loop once you have what you need.
{% endif %}
```

- [ ] **Step 3: Write `guides/crud.md.jinja`** (only the verbs that exist)

```jinja
{% if has_docs | default(false) %}# CRUD operations

End-to-end create, read, update, and delete for the `{{ showcase.attr }}` resource. Browse
the full operation list in the **[API Reference](../reference/)**.

```python
from {{ package }}.extras.facade import Client

client = Client.from_env()
```
{% set ops = showcase.operations %}
{% if showcase.has_create %}
## Create

```python
created = client.{{ showcase.attr }}.{{ ops["create"].method }}(
{% for a in ops["create"].required_args %}{% if a.kind == "body" %}    {{ a.name }}={{ a.body_model }}(...),
{% else %}    {{ a.name }}="{{ a.placeholder }}",
{% endif %}{% endfor %})
```
{% endif %}
{% if showcase.has_read %}
## Read

```python
fetched = client.{{ showcase.attr }}.{{ ops["read"].method }}(
{% for a in ops["read"].required_args %}{% if a.kind == "body" %}    {{ a.name }}={{ a.body_model }}(...),
{% else %}    {{ a.name }}="{{ a.placeholder }}",
{% endif %}{% endfor %})
```
{% endif %}
{% if showcase.has_update %}
## Update

```python
updated = client.{{ showcase.attr }}.{{ ops["update"].method }}(
{% for a in ops["update"].required_args %}{% if a.kind == "body" %}    {{ a.name }}={{ a.body_model }}(...),
{% else %}    {{ a.name }}="{{ a.placeholder }}",
{% endif %}{% endfor %})
```
{% endif %}
{% if showcase.has_delete %}
## Delete

```python
client.{{ showcase.attr }}.{{ ops["delete"].method }}(
{% for a in ops["delete"].required_args %}{% if a.kind == "body" %}    {{ a.name }}={{ a.body_model }}(...),
{% else %}    {{ a.name }}="{{ a.placeholder }}",
{% endif %}{% endfor %})
```
{% endif %}
{% endif %}
```

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/scaffold/docs/guides/
git commit -m "feat(sdk): emit auth, pagination, and CRUD how-to guides"
```

### Task 10: Reference generator (`gen_ref_pages.py.jinja`)

**Files:**
- Create: `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja`

- [ ] **Step 1: Write `scripts/gen_ref_pages.py.jinja`** (api + models only — decision #8)

```jinja
{% if has_docs | default(false) %}"""Generate the API Reference: one mkdocstrings page per api/ and models/ module."""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

PACKAGE = "{{ package }}"
SUBPACKAGES = ("api", "models")

src = Path(__file__).resolve().parent.parent / PACKAGE
assert src.is_dir(), src  # fail loudly if the package path drifts

nav = mkdocs_gen_files.Nav()
for sub in SUBPACKAGES:
    for path in sorted((src / sub).rglob("*.py")):
        module = path.relative_to(src).with_suffix("")
        parts = tuple(module.parts)
        # Skip the api/ and models/ __init__ aggregators (they re-export every
        # member; documenting them re-renders everything) and private modules.
        if parts[-1] == "__init__" or parts[-1].startswith("_"):
            continue
        doc_path = Path(*parts).with_suffix(".md")
        full = Path("reference", doc_path)
        nav[parts] = doc_path.as_posix()
        with mkdocs_gen_files.open(full, "w") as fd:
            fd.write(f"::: {'.'.join((PACKAGE, *parts))}\n")
        mkdocs_gen_files.set_edit_path(full, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as fd:
    fd.writelines(nav.build_literate_nav())
{% endif %}
```

> **Verified (spike round 2):** skipping `__init__` yields per-module pages only
> (no `__init__`-titled nav leaves, no `index.md` for `section-index` to need).
> Confirmed 414 reference pages, 0 broken pages, `mkdocs build --strict` exit 0.

- [ ] **Step 2: Commit**

```bash
git add src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja
git commit -m "feat(sdk): emit gen-files reference generator (api + models)"
```

---

## Phase 5 — Scaffold wiring (gate existing always-emitted files)

### Task 11: `mkdocs.yml`, `pyproject`, `noxfile`, `docs.yml`

**Files:**
- Modify: `src/phantasos/scaffold/mkdocs.yml.jinja`
- Modify: `src/phantasos/scaffold/pyproject.toml.jinja`
- Modify: `src/phantasos/scaffold/noxfile.py.jinja`
- Modify: `src/phantasos/scaffold/.github/workflows/docs.yml.jinja`

- [ ] **Step 1: Replace `mkdocs.yml.jinja` entirely** (gated; verified config)

```jinja
{% if has_docs | default(false) %}site_name: {{ site_name }}
site_description: {{ description }}
repo_url: {{ repo_url }}
repo_name: {{ repo_url | replace("https://github.com/", "") }}

theme:
  name: material
  features:
    - content.code.copy
    - navigation.instant
    - navigation.sections
    - navigation.top
    - search.suggest
    - toc.follow
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      toggle: {icon: material/brightness-7, name: Switch to dark mode}
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      toggle: {icon: material/brightness-4, name: Switch to light mode}

nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Architecture: architecture.md
  - Guides:
{% if has_auth %}      - Authentication: guides/authentication.md
{% endif %}{% if show_pagination_guide %}      - Pagination: guides/pagination.md
{% endif %}      - CRUD operations: guides/crud.md
  - API Reference: reference/

exclude_docs: |
  _hooks.py
  scripts/

hooks:
  - docs/_hooks.py

plugins:
  - search
  - gen-files:
      scripts: [docs/scripts/gen_ref_pages.py]
  - literate-nav:
      nav_file: SUMMARY.md
  - mkdocstrings:
      handlers:
        python:
          paths: ["."]
          inventories:
            - https://docs.python.org/3/objects.inv
            - https://docs.pydantic.dev/latest/objects.inv
          options:
            docstring_style: sphinx
            filters:
              - "!^_"
              - "!_with_http_info$"
              - "!_without_preload_content$"
              - "!_serialize$"
            show_bases: false
            show_source: false
            show_root_heading: true
            show_docstring_parameters: false
            members_order: source

markdown_extensions:
  - admonition
  - pymdownx.highlight
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - toc:
      permalink: true
{% endif %}
```

> **Verified config (spike round 2, full 14 api + 401 model tree, strict exit 0):**
> - `show_bases: false` + `inventories:` (python + pydantic) eliminate the
>   external-base cross-reference warnings that would otherwise abort `--strict`.
> - `show_docstring_parameters: false` drops the internal `_request_timeout`/
>   `_headers` param noise (signatures keep their types) and shrinks the
>   cross-ref surface.
> - **No `section-index`** (reference emits per-module pages only).
> - `exclude_docs` keeps `_hooks.py` + `scripts/` out of the built `site/`.
> - `hooks: [docs/_hooks.py]` and `scripts: [docs/scripts/gen_ref_pages.py]`
>   resolve relative to the mkdocs.yml dir (SDK root) — matching the emitted
>   `docs/_hooks.py` and `docs/scripts/gen_ref_pages.py`.

- [ ] **Step 2: Add the gated `docs` dependency group to `pyproject.toml.jinja`**

After the `dev` group line (line 34), add:

```jinja
{% if has_docs | default(false) %}docs = [
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.26",
    "mkdocs-gen-files>=0.5",
    "mkdocs-literate-nav>=0.6",
]
{% endif %}
```

Insert it as the **last** entry under `[dependency-groups]` (immediately after the `dev = [...]` line, which is currently the last group). The `dev` line is the anchor — keep it intact.

- [ ] **Step 3: Add gated docs sessions to `noxfile.py.jinja`**

Append:

```jinja
{% if has_docs | default(false) %}

@nox.session
def docs(session: nox.Session) -> None:
    session.run_install(
        "uv", "sync", "--group", "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("mkdocs", "build", "--strict")


@nox.session(name="docs-serve")
def docs_serve(session: nox.Session) -> None:
    session.run_install(
        "uv", "sync", "--group", "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("mkdocs", "serve")
{% endif %}
```

- [ ] **Step 4: Gate `.github/workflows/docs.yml.jinja`**

The file is **already** wrapped in `{% raw %}…{% endraw %}` (to preserve GitHub's
`${{ … }}` expressions) and its build step **already** runs
`uv run --group docs mkdocs build --strict`. So the ONLY change is the gate, and
it MUST go OUTSIDE the raw block (a `{% if %}` placed inside `{% raw %}` is
emitted literally and never evaluates). Read the file, then:

1. Add a new first line: `{% if has_docs | default(false) %}`
2. Add a new last line: `{% endif %}`

The existing `{% raw %}` becomes the second line and `{% endraw %}` the
second-to-last. Do not change the YAML body or the build command.

- [ ] **Step 4b: Update the existing scaffold test for the now-gated files**

`tests/test_scaffold.py::test_builtin_workflows_render_valid_yaml` (lines
123-160) renders the builtin scaffold WITHOUT `has_docs` and asserts `docs.yml`
is emitted (line 155) and parses `mkdocs.yml` (line 160) — both are now gated and
will be absent, failing the test. Make its `ctx` opt into docs so those files are
emitted and validated: add these keys to the `ctx` dict (after `config_class_name`):

```python
        "has_docs": True,
        "site_name": "acme-sdk",
        "show_pagination_guide": True,
```

(No other `test_scaffold.py` test reads `mkdocs.yml`/`docs.yml`; the rest just
need `| default(false)` gating, already in the templates, to keep rendering.)

- [ ] **Step 5: Run the offline gate**

Run: `uv run nox -s gate`
Expected: PASS (existing scaffold tests + new docs tests green).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/scaffold/mkdocs.yml.jinja src/phantasos/scaffold/pyproject.toml.jinja src/phantasos/scaffold/noxfile.py.jinja src/phantasos/scaffold/.github/workflows/docs.yml.jinja tests/test_scaffold.py
git commit -m "feat(sdk): gate docs scaffold wiring on has_docs (mkdocs/deps/nox/CI)"
```

---

## Phase 6 — Opt prisma-browser in

### Task 12: Add `docs:` to prisma-browser + offline emission tests

**Files:**
- Modify: `products/prisma-browser/sdk.yml`
- Create: `tests/test_sdk_docs_emitted.py`

- [ ] **Step 1: Write the failing emission test** (renders the scaffold with a synthetic docs context — no OAG build needed)

```python
# tests/test_sdk_docs_emitted.py
from pathlib import Path

from phantasos import scaffold


def _ctx(**over):
    base = {
        "package": "prisma_browser", "library": "urllib3",
        "base_url": "https://x", "spec_version": "1", "spec_title": "Prisma",
        "has_auth": True, "has_pagination": True, "has_errors": True,
        "has_facade": True, "has_retry": True, "has_docs": True,
        "config_class_name": "C", "distribution": "prisma-browser-sdk",
        "description": "d", "author": "A", "author_email": "a@b.c",
        "repo_url": "https://github.com/x/y", "license": "Apache-2.0",
        "python_versions": ["3.12"], "dependencies": [],
        "site_name": "prisma-browser-sdk",
        "credentials": [
            {"name": "client_id", "env_var": "CLIENT_ID", "secret": False, "required": True},
            {"name": "client_secret", "env_var": "CLIENT_SECRET", "secret": True, "required": True},
        ],
        "show_pagination_guide": True,
        "showcase": {
            "attr": "applications", "has_create": True, "has_read": True,
            "has_list": True, "has_update": False, "has_delete": True,
            "list": {"method": "list_applications"},
            "operations": {
                "create": {"method": "create_application", "required_args": [
                    {"name": "type", "kind": "path", "placeholder": "WEB"},
                    {"name": "create_or_replace_app_input", "kind": "body", "body_model": "CreateOrReplaceAppInput"}]},
                "read": {"method": "get_application_by_id", "required_args": [
                    {"name": "id", "kind": "path", "placeholder": "<id>"}]},
                "list": {"method": "list_applications", "required_args": []},
                "delete": {"method": "delete_application_by_id", "required_args": [
                    {"name": "id", "kind": "path", "placeholder": "<id>"}]},
            },
        },
    }
    base.update(over)
    return base


def test_docs_emitted_when_has_docs(tmp_path):
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    assert "create_application" in crud
    assert "get_application_by_id" in crud
    assert "delete_application_by_id" in crud
    # update omitted (has_update False) -> no patch example
    assert "## Update" not in crud
    assert (tmp_path / "mkdocs.yml").exists()
    assert "docstring_style: sphinx" in (tmp_path / "mkdocs.yml").read_text()
    assert (tmp_path / "docs/_hooks.py").exists()
    auth = (tmp_path / "docs/guides/authentication.md").read_text()
    assert "CLIENT_SECRET" in auth


def test_no_docs_when_flag_false(tmp_path):
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx(has_docs=False))
    assert not (tmp_path / "mkdocs.yml").exists()
    assert not (tmp_path / "docs").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sdk_docs_emitted.py -q`
Expected: FAIL initially if any template path/name mismatches — fix templates until green. (This is the offline acceptance test for Phase 4/5.)

- [ ] **Step 3: Add the `docs:` block to `products/prisma-browser/sdk.yml`**

After the `facade: true` line, add:

```yaml
docs:
  showcase_resource: applications
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sdk_docs_emitted.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the offline gate**

Run: `uv run nox -s gate`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add products/prisma-browser/sdk.yml tests/test_sdk_docs_emitted.py
git commit -m "feat(sdk): opt prisma-browser into generated docs + emission tests"
```

---

## Phase 7 — Integration gate

### Task 13: `nox -s sdk-docs` — real SDK → real docs → `mkdocs build --strict`

**Files:**
- Modify: `noxfile.py`

> **NAME COLLISION — do NOT call this `docs`.** `noxfile.py` already defines a
> `docs` session (lines 121-125) and `docs-serve` (128-132) that build
> *phantasos's own* site, and `"docs"` is in `nox.options.sessions` (line 29,
> the default/CI set). A second `def docs` would silently replace it and force
> Java+network onto the default gate. Name the new session **`sdk-docs`** and do
> NOT add it to `nox.options.sessions` (it's opt-in, like `live`/`smoke`).

- [ ] **Step 1: Read the existing `live`/`smoke` sessions** in `noxfile.py` to mirror their venv backend, env handling, and skip-without-prereqs pattern. Confirm the existing `docs` session and `nox.options.sessions` contents (do not modify them).

- [ ] **Step 2: Add an `sdk-docs` session** that builds prisma-browser with docs and strict-builds the site

```python
@nox.session(name="sdk-docs", venv_backend="uv")
def sdk_docs(session: nox.Session) -> None:
    """Build the prisma-browser SDK + its docs and run `mkdocs build --strict`.

    Integration gate (opt-in; needs the OAG JRE + network, self-provisioned like
    `smoke`). NOT added to nox.options.sessions, so the default `nox`/CI run is
    unaffected and phantasos's own `docs` session stays intact.
    """
    import os

    from phantasos.productconfig import load_product

    session.install("-e", ".")
    session.run("phantasos", "sdk", "build", "prisma-browser", "--no-smoke")
    out = load_product("prisma-browser").output_dir
    session.chdir(str(out))
    session.run(
        "uv", "run", "--group", "docs", "mkdocs", "build", "--strict",
        external=True, env={**os.environ},
    )
    assert (out / "site" / "reference").exists(), "reference pages were not generated"
```

(Adjust `install`/`run` to match the repo's existing session conventions found in
Step 1; the essential acceptance is: build the SDK, then `mkdocs build --strict`
in its dir succeeds and `site/reference/` exists.)

- [ ] **Step 3: Run the integration gate**

Run: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-cli NOX_ENVDIR=/tmp/phantasos-nox; uv run nox -s sdk-docs`
Expected: SDK builds; `mkdocs build --strict` exits 0; `site/reference/` exists. Capture and show the real tail of the output (evidence before assertion).

- [ ] **Step 4: Commit**

```bash
git add noxfile.py
git commit -m "test(sdk): add docs integration gate (real SDK -> strict mkdocs build)"
```

---

## Phase 8 — Docs, context, changelog

### Task 14: Deep-dive + CHANGELOG

**Files:**
- Modify: `.agents/context/sdk-generator.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update the deep-dive narrative** — add the docs stage to the pipeline description (stage 4a: scoped introspect + docs context; gated scaffold templates; the strict-build hook). Keep it factual.

- [ ] **Step 2: Refresh generated blocks**

Run: `uv run nox -s context`
Then verify: `uv run nox -s context -- --check`
Expected: both succeed.

- [ ] **Step 3: Add a `## [Unreleased]` CHANGELOG entry**

```markdown
- Generated SDKs can now ship a complete Material for MkDocs site (Getting Started,
  Architecture, authentication/pagination/CRUD how-to guides, and an mkdocstrings API
  reference). Opt in per product via a `docs:` block naming a `showcase_resource`; the
  guides are tailored to that resource via a scoped, build-time introspection. The site
  builds under `mkdocs build --strict`. Products without a `docs:` block emit no docs
  (and no longer ship the previously non-building mkdocs shell).
```

- [ ] **Step 4: Run the full offline gate + context check**

Run: `uv run nox -s gate && uv run nox -s context -- --check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .agents/context/sdk-generator.md CHANGELOG.md
git commit -m "docs(sdk): document the generated-docs stage + CHANGELOG entry"
```

---

## Final verification (before PR)

- [ ] `uv run nox -s gate` — green (ruff/format/mypy/pytest).
- [ ] `uv run nox -s context -- --check` — generated blocks in sync.
- [ ] `uv run nox -s sdk-docs` — real SDK builds docs under `--strict` (show output).
- [ ] `uv run nox -s docs` — phantasos's OWN docs still build (the session was not clobbered).
- [ ] `uv run nox -s live` — unaffected / still green.
- [ ] `git diff develop...HEAD --stat` — only intended files; `version` unchanged; CHANGELOG under `[Unreleased]`.
- [ ] Open PR with `gh pr create --base develop` (squash-merge). Do NOT target `main`.

## Self-review notes (author)

- **Spec coverage:** config (Task 1-2), scoped introspect + classification (Task 3-5), build wiring (Task 6), all pages incl. reference + hook (Task 7-10), gating of mkdocs/deps/nox/CI (Task 11), prisma-browser opt-in (Task 12), strict integration gate (Task 13), deep-dive + CHANGELOG (Task 14). All §1-§10 spec items mapped.
- **Type consistency:** `classify_operations(ops, resource, overrides) -> dict[slot,OperationInfo]`; `shape_context(...) -> dict` with keys `has_docs/site_name/showcase/credentials/show_pagination_guide`; `build_docs_context(loaded, project_dir)`. Template context keys match the test fixtures in Task 12.
- **Open polish (non-blocking):** `show_docstring_parameters: false` for a cleaner reference is left default-on; revisit if the rendered param tables look noisy in Task 13's output.
```
