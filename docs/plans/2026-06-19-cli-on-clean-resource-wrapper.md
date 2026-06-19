# CLI on the clean resource wrapper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every generated SDK a typed `client.<resource>.<verb>(...)` wrapper that is the single source of truth, and re-base the generated CLI to introspect and dispatch through that wrapper instead of the raw OpenAPI-Generator `*Api` classes.

**Architecture:** A new build-time **wrapper generator** (stage 1) renders typed resource classes from a **shared op-model** (`generator/opmodel/`, promoted from today's `cli/classify.py`+`introspect.py`+`inventory.py`). The facade binds `client.<resource>` to the wrapper and keeps `_RESOURCES` as the raw-class map. The CLI generator (stage 2) re-introspects the wrapper and dispatches clean method names; dry-run uses a private `resource._serialize(verb, **kwargs)` seam; HTTP capture wraps the facade `api_client`. Naming is overridable via a new `sdk.yml operations:` block; `cli.yml` stays an independent CLI-presentation layer.

**Tech Stack:** Python 3.12+, pydantic v2, Jinja2 templates, urllib3-based generated SDKs, Typer+Rich CLIs, OpenAPI Generator 7.22.0 (wrapped), `uv` + `nox`, pytest.

**Reference spec:** `docs/specs/2026-06-19-cli-on-clean-resource-wrapper-design.md` (D1–D11). Read it first.

## Global Constraints

- **Run uv/nox with an explicit env dir** (sshfs): prefix commands with
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup`; for venv-backed nox sessions
  also `NOX_ENVDIR=/tmp/phantasos-nox`.
- **Offline gate must stay green** after every task: `uv run nox -s gate`
  (ruff + ruff format + mypy + pytest).
- **Generated artifact is disposable** — never hand-edit `*-sdk/` output; all
  durable changes live in `src/phantasos/` and `products/<name>/`.
- **Frozen oracles** (`.claude/harness.toml` `protected_globs`): live-CRUD
  template, `tests/acceptance/**`, `.claude/**`. NEVER edit to make work pass.
- **No new runtime deps** in generated SDKs beyond `urllib3`,
  `python-dateutil`, `pydantic`, `typing-extensions`.
- **Branch:** `feature/sdk-cleanup` off `develop`; squash-merge → `develop`;
  no version bump; record under `## [Unreleased]` in `CHANGELOG.md`.
- **Test policy:** real dependencies, evidence before assertions, behavioural
  tests through the emitted package (`tests/test_cli_emitted.py` `emitted`
  fixture; config cached at import — set env BEFORE `importlib.import_module`).

---

## File Structure (decomposition)

**New:**
- `src/phantasos/generator/opmodel/__init__.py` — shared op-model package.
- `src/phantasos/generator/opmodel/classify.py` — pure classification core (moved
  from `cli/classify.py`): `classify_name`, `_strip_id_suffix`, `_singularize`,
  `detect_id_param`, plus the new `CLEAN_VERB_TABLE` for clean-name input.
- `src/phantasos/generator/opmodel/introspect.py` — moved from `cli/introspect.py`;
  parameterised over which registry/classes to walk.
- `src/phantasos/generator/opmodel/inventory.py` — moved from `cli/inventory.py`.
- `src/phantasos/generator/sdk/wrapper.py` — builds the wrapper render context from
  an `OperationInventory` + the resolved `operations` overrides; collision gate.
- `src/phantasos/generator/sdk/components/facade/resource.py.jinja` — the typed
  resource-wrapper template.
- `tests/test_opmodel_classify.py`, `tests/test_sdk_wrapper.py`,
  `tests/test_sdk_operations_override.py`, `tests/golden/` (snapshot fixtures).

**Modified:**
- `src/phantasos/generator/cli/classify.py` — re-export from `opmodel` (thin shim
  during P1), then consume clean-name classification.
- `src/phantasos/generator/cli/introspect.py` — thin re-export of `opmodel`.
- `src/phantasos/generator/sdk/components/facade/client.py.jinja` — bind wrappers,
  keep `_RESOURCES`.
- `src/phantasos/generator/sdk/render.py` — vendor the resource template;
  `_discover_resources` feeds wrapper-gen.
- `src/phantasos/generator/sdk/build.py` — new "introspect→classify→render wrapper"
  sub-step after OAG.
- `src/phantasos/config.py` + `src/phantasos/productconfig.py` — `OperationsOverride`
  model + `operations:` on `ProductConfig`.
- `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — dispatch
  clean methods; dry-run via seam; capture facade; drop paginate composition.

---

## Task 0: Golden retain oracle (`cli discover` snapshots)

**Files:**
- Create: `tests/golden/prisma-browser.discover.txt`, `tests/golden/posture.discover.txt`
- Create: `tests/test_cli_discover_golden.py`

**Interfaces:**
- Consumes: built SDKs at `../prisma-browser-sdk`, `../posture-sdk`; the CLI
  generator's `cli discover` (`phantasos cli discover <product>`).
- Produces: `tests/golden/<product>.discover.txt` — the immutable retain oracle
  later tasks must reproduce.

- [ ] **Step 1: Build both SDKs from this branch's specs**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build prisma-browser --no-smoke
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build posture --no-smoke
```
Expected: `built prisma_browser: …` and `built posture: …`.

- [ ] **Step 2: Capture the current discover output as golden fixtures**

```bash
mkdir -p tests/golden
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos cli discover prisma-browser > tests/golden/prisma-browser.discover.txt
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos cli discover posture > tests/golden/posture.discover.txt
```

- [ ] **Step 3: Write the golden test (passes now; is the retain contract later)**

```python
# tests/test_cli_discover_golden.py
import subprocess
from pathlib import Path
import pytest

GOLDEN = Path(__file__).parent / "golden"
PRODUCTS = [("prisma-browser", "../prisma-browser-sdk"), ("posture", "../posture-sdk")]


@pytest.mark.parametrize("product, sdk_rel", PRODUCTS)
def test_cli_discover_matches_golden(product: str, sdk_rel: str) -> None:
    if not (Path(__file__).parent.parent / sdk_rel).exists():
        pytest.skip(f"{product} SDK not built")
    out = subprocess.run(
        ["uv", "run", "phantasos", "cli", "discover", product],
        capture_output=True, text=True, check=True,
    ).stdout
    expected = (GOLDEN / f"{product}.discover.txt").read_text()
    assert out == expected, f"{product} command tree drifted from golden oracle"
```

- [ ] **Step 4: Run it — must pass against current (raw-`*Api`) CLI**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_discover_golden.py -v`
Expected: 2 passed (or skipped if an SDK is missing).

- [ ] **Step 5: Commit**

```bash
git add tests/golden tests/test_cli_discover_golden.py
git commit -m "test(cli): golden cli-discover snapshots as the retain oracle"
```

> NOTE: the golden output's *command tree* (paths/flags/columns/help) is the
> contract. If P4 legitimately changes a non-semantic detail (e.g. a help string
> the raw method's docstring fed), re-capture the golden in P5 and record the diff
> in the PR — do NOT silently overwrite mid-flight.

---

## Task 1: Promote the op-model to a shared module

Pure relocation (no behaviour change) + a clean-name classification table the
wrapper-gen and the wrapper-introspecting CLI will both need.

**Files:**
- Create: `src/phantasos/generator/opmodel/__init__.py`,
  `opmodel/classify.py`, `opmodel/introspect.py`, `opmodel/inventory.py`
- Modify: `src/phantasos/generator/cli/classify.py`,
  `cli/introspect.py`, `cli/inventory.py` (become re-export shims)
- Test: `tests/test_opmodel_classify.py`

**Interfaces:**
- Consumes: today's `cli/classify.py` functions verbatim.
- Produces: `opmodel.classify.classify_name(method: str) -> Classification | None`
  (unchanged); NEW `opmodel.classify.classify_clean(method: str) -> Classification | None`
  for clean method-name input (`get`/`list`/`create`/`update`/`delete`/non-CRUD);
  `opmodel.introspect.introspect(package, sdk_path, *, registry_attr="_RESOURCES")`.

- [ ] **Step 1: Move the three modules, leave re-export shims**

```bash
mkdir -p src/phantasos/generator/opmodel
git mv src/phantasos/generator/cli/inventory.py src/phantasos/generator/opmodel/inventory.py
git mv src/phantasos/generator/cli/introspect.py src/phantasos/generator/opmodel/introspect.py
```
Split `cli/classify.py`: the **pure** helpers (`classify_name`, `_strip_id_suffix`,
`_singularize`, `detect_id_param`, `Classification`, `_VERB_PREFIXES`,
`_SKIP_FRAGMENTS`) move to `opmodel/classify.py`; `build_cli_ir` and the
CLI-specific helpers STAY in `cli/classify.py` and import from `opmodel`.

Create `src/phantasos/generator/opmodel/__init__.py`:
```python
from .classify import Classification, classify_clean, classify_name, detect_id_param
from .introspect import introspect
from .inventory import FieldInfo, OperationInfo, OperationInventory, ParamInfo

__all__ = [
    "Classification", "classify_clean", "classify_name", "detect_id_param",
    "introspect", "FieldInfo", "OperationInfo", "OperationInventory", "ParamInfo",
]
```

- [ ] **Step 2: Add re-export shims so existing imports keep working**

`cli/introspect.py` becomes:
```python
from ..opmodel.introspect import *  # noqa: F401,F403
from ..opmodel.introspect import introspect  # explicit for mypy
```
`cli/inventory.py`:
```python
from ..opmodel.inventory import *  # noqa: F401,F403
from ..opmodel.inventory import (  # explicit re-exports
    FieldInfo, OperationInfo, OperationInventory, ParamInfo,
)
```
`cli/classify.py` keeps `build_cli_ir` etc., adds at top:
```python
from ..opmodel.classify import (
    Classification, _singularize, _strip_id_suffix, classify_name, detect_id_param,
)
```

- [ ] **Step 3: Make `opmodel.introspect.introspect` parameterisable**

In `opmodel/introspect.py::_introspect`, change the hard-coded
`resources = facade._RESOURCES` to read a configurable attribute, defaulting to
the existing behaviour:
```python
def introspect(package: str, sdk_path: Path, *, registry_attr: str = "_RESOURCES") -> OperationInventory:
    ...  # sys.path handling unchanged
def _introspect(package: str, sdk_path: Path, registry_attr: str) -> OperationInventory:
    pkg = importlib.import_module(package)
    facade = importlib.import_module(f"{package}.extras.facade")
    resources: dict[str, type[Any]] = getattr(facade, registry_attr)
    ...
```

- [ ] **Step 4: Add the clean-name classification table + `classify_clean`**

```python
# opmodel/classify.py — clean method names map DIRECTLY to (verb, sub_verb)
_CLEAN_VERBS: dict[str, tuple[Verb, SubVerb]] = {
    "create": ("create", "create"),
    "update": ("update", "update"),   # wrapper exposes one `update`
    "delete": ("delete", "delete"),
    "get": ("show", "get"),
    "list": ("show", "list"),
}


def classify_clean(method: str) -> Classification | None:
    """Classify a CLEAN wrapper method name. CRUD verbs map directly; any other
    (non-CRUD) method is a `request`-namespace action (object filled by caller)."""
    if method in _CLEAN_VERBS:
        verb, sub = _CLEAN_VERBS[method]
        return Classification(verb=verb, sub_verb=sub, object="")  # object set by resource
    return None  # non-CRUD → handled as request action by build_cli_ir
```

- [ ] **Step 5: Test — old behaviour preserved, new function works**

```python
# tests/test_opmodel_classify.py
from phantasos.generator.opmodel.classify import classify_name, classify_clean


def test_classify_name_unchanged():
    c = classify_name("create_applications")
    assert (c.verb, c.sub_verb, c.object) == ("create", "create", "application")
    assert classify_name("upload_background_image") is None  # non-CRUD stays unmapped


def test_classify_clean_direct_mapping():
    assert classify_clean("get").verb == "show"
    assert classify_clean("list").sub_verb == "list"
    assert classify_clean("create").verb == "create"
    assert classify_clean("suspend") is None  # non-CRUD → request namespace
```

- [ ] **Step 6: Run the full gate (proves the move broke nothing)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate`
Expected: all green (existing CLI tests import through the shims unchanged).

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/generator/opmodel src/phantasos/generator/cli tests/test_opmodel_classify.py
git commit -m "refactor(gen): promote op-model (classify/introspect/inventory) to shared generator/opmodel"
```

---

## Task 2: `sdk.yml operations:` naming override

**Files:**
- Modify: `src/phantasos/config.py` (or `productconfig.py` where `ProductConfig`
  lives — grep `class ProductConfig`)
- Test: `tests/test_sdk_operations_override.py`

**Interfaces:**
- Produces: `OperationsOverride` pydantic model and `ProductConfig.operations:
  dict[str, OperationOverride]`; a resolver `resolve_operation_overrides(inv,
  overrides) -> dict[op_key, ResolvedNaming]` applied in wrapper-gen (Task 3).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sdk_operations_override.py
import pytest
from pydantic import ValidationError
from phantasos.config import OperationOverride


def test_operation_override_fields():
    o = OperationOverride(resource="application", method="get_by_type", verb="show")
    assert o.resource == "application" and o.method == "get_by_type"


def test_operation_override_rejects_unknown_field():
    with pytest.raises(ValidationError):
        OperationOverride(resourse="typo")  # extra=forbid
```

- [ ] **Step 2: Run — fails (model missing)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_sdk_operations_override.py -v`
Expected: ImportError / fails.

- [ ] **Step 3: Add the model + wire into ProductConfig**

```python
# src/phantasos/config.py
from typing import Literal

class OperationOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    resource: str | None = None          # client.<resource> attribute
    method: str | None = None            # clean method name
    verb: Literal["create", "update", "delete", "show", "request"] | None = None
```
In `ProductConfig` (grep its definition):
```python
    operations: dict[str, OperationOverride] = Field(default_factory=dict)
```
Key = operationId, or `"<METHOD> <path>"` (e.g. `"GET /addresses"`) fallback.

- [ ] **Step 4: Add the resolver + build-time validation**

```python
# src/phantasos/generator/sdk/wrapper.py  (created here, expanded in Task 3)
def resolve_overrides(operation_ids: set[str], overrides: dict[str, OperationOverride]) -> None:
    """Fail the build on an override that names no real operation."""
    unknown = set(overrides) - operation_ids
    if unknown:
        raise ValueError(
            f"sdk.yml operations: unknown operation key(s): {', '.join(sorted(unknown))}"
        )
```

- [ ] **Step 5: Test the validation + run**

```python
def test_unknown_operation_key_fails(tmp_path):
    from phantasos.generator.sdk.wrapper import resolve_overrides
    from phantasos.config import OperationOverride
    with pytest.raises(ValueError, match="unknown operation key"):
        resolve_overrides({"GetAddresses"}, {"NopeOp": OperationOverride(method="x")})
```
Run the file; expected PASS.

- [ ] **Step 6: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/config.py src/phantasos/generator/sdk/wrapper.py tests/test_sdk_operations_override.py
git commit -m "feat(sdk): sdk.yml operations override model + build-time validation"
```

---

## Task 3: Stage-1 typed resource-wrapper generation

The core task. Build the wrapper render context from introspection + overrides,
render the typed template, bind it in the facade, wire it into `build.py`, and
gate on name collisions.

### Task 3.1 — Wrapper render context

**Files:**
- Modify: `src/phantasos/generator/sdk/wrapper.py`
- Test: `tests/test_sdk_wrapper.py`

**Interfaces:**
- Consumes: `opmodel.introspect.introspect`, `opmodel.classify.classify_name`,
  `OperationOverride`.
- Produces: `build_wrapper_context(inv: OperationInventory, overrides) ->
  list[ResourceView]` where each `ResourceView` has `attr` (client.<attr>),
  `cls` (raw `*Api` class name), `module`, and `methods: list[WrapperMethod]`.
  `WrapperMethod` = `{name, kind ("create"/"get"/"list"/"update"/"delete"/"action"),
  raw_method, params: list[ParamView], body_param, body_model, return_model,
  serialize_name, get_bindings: list[GetBinding] | None}`.

- [ ] **Step 1: Failing test — context groups ops into clean methods + collapses GET**

```python
# tests/test_sdk_wrapper.py — uses the real built prisma-browser SDK
from pathlib import Path
import pytest
from phantasos.generator.opmodel import introspect
from phantasos.generator.sdk.wrapper import build_wrapper_context

SDK = Path(__file__).parent.parent / "prisma-browser-sdk"


@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_wrapper_context_has_clean_crud():
    inv = introspect("prisma_browser", SDK)
    views = {v.attr: v for v in build_wrapper_context(inv, overrides={})}
    dg = views["device_groups"]
    names = {m.name for m in dg.methods}
    assert {"create", "get", "list", "update", "delete"} <= names
    assert "create_device_group" not in names          # raw name gone
    assert "get_by_type" not in names                  # folded into .get
    get = next(m for m in dg.methods if m.name == "get")
    assert get.kind == "get" and get.get_bindings is not None   # multi-binding GET
```

- [ ] **Step 2: Run — fails (function missing)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_sdk_wrapper.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `build_wrapper_context`**

```python
# src/phantasos/generator/sdk/wrapper.py
from dataclasses import dataclass, field
from ..opmodel.classify import classify_name, _strip_id_suffix, _singularize, detect_id_param
from ..opmodel.inventory import OperationInventory, OperationInfo

@dataclass
class GetBinding:
    raw_method: str
    requires: list[str]          # required path params selecting this binding
    serialize_name: str

@dataclass
class WrapperMethod:
    name: str
    kind: str                    # create|get|list|update|delete|action
    raw_method: str
    params: list[object]         # ParamView; see template needs
    body_param: str | None
    body_model: str | None
    return_model: str | None
    serialize_name: str
    get_bindings: list[GetBinding] | None = None
    paginated: bool = False

@dataclass
class ResourceView:
    attr: str
    cls: str
    module: str
    methods: list[WrapperMethod] = field(default_factory=list)


def build_wrapper_context(inv: OperationInventory, overrides: dict) -> list[ResourceView]:
    resolve_overrides({op.method for r in inv.operations for op in [r]} | _op_ids(inv), overrides)
    views: dict[str, ResourceView] = {}
    get_family: dict[tuple[str, str], list[OperationInfo]] = {}  # (attr, "get") -> ops
    for op in inv.operations:
        cls_view = _resolve_naming(op, overrides)   # -> (attr, method_name, kind)
        rv = views.setdefault(op.resource, ResourceView(attr=op.resource, cls=_cls_for(op), module=_module_for(op)))
        if cls_view.kind == "get":
            get_family.setdefault((rv.attr, "get"), []).append(op)
            continue
        rv.methods.append(_method_from(op, cls_view))
    # collapse the GET family into a single `.get` per resource
    for (attr, _), ops in get_family.items():
        views[attr].methods.append(_collapse_get(ops))
    _gate_collisions(views)
    return list(views.values())
```
(Implement `_resolve_naming` — heuristic via `classify_name`, then apply
`overrides`; `_collapse_get` — union the get-family params, build `GetBinding`
per op sorted by `requires` length; `_gate_collisions` — raise `ValueError` on
two methods sharing a name within a resource. Helper detail in Step 4.)

- [ ] **Step 4: Implement the helpers (collapse + collision gate)**

```python
def _collapse_get(ops: list[OperationInfo]) -> WrapperMethod:
    # union of every get-op's params (id + discriminators + query filters), all optional
    seen, params = set(), []
    bindings = []
    for op in sorted(ops, key=lambda o: len([p for p in o.params if p.location == "path"])):
        bindings.append(GetBinding(op.method, [p.name for p in op.params if p.location == "path"],
                                    f"_{op.method}_serialize"))
        for p in op.params:
            if p.name not in seen:
                seen.add(p.name); params.append(p)
    item = ops[0].return_model
    return WrapperMethod(name="get", kind="get", raw_method=bindings[0].raw_method,
                         params=params, body_param=None, body_model=None,
                         return_model=item, serialize_name=bindings[0].serialize_name,
                         get_bindings=bindings)


def _gate_collisions(views: dict[str, ResourceView]) -> None:
    for rv in views.values():
        names = [m.name for m in rv.methods]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(
                f"resource '{rv.attr}': method name collision {sorted(dupes)} — "
                f"disambiguate via sdk.yml operations:"
            )
```

- [ ] **Step 5: Run the test — passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_sdk_wrapper.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/sdk/wrapper.py tests/test_sdk_wrapper.py
git commit -m "feat(sdk): wrapper render context (clean CRUD + collapsed .get + collision gate)"
```

### Task 3.2 — The typed wrapper template + `_serialize` seam

**Files:**
- Create: `src/phantasos/generator/sdk/components/facade/resource.py.jinja`
- Modify: `src/phantasos/generator/sdk/render.py` (vendor it)
- Test: `tests/test_render.py` (extend)

**Interfaces:**
- Produces: `<pkg>/extras/resources.py` with one `class <Resource>Resource` per
  resource, each exposing typed `create/get/list/update/delete`/non-CRUD methods,
  a private `_serialize(verb, **kwargs) -> tuple` seam, and `__init__(self, api)`.

- [ ] **Step 1: Write the template** (`resource.py.jinja`)

```jinja
"""Typed resource wrappers (vendored by phantasos). client.<resource> is one of these."""
from __future__ import annotations
from typing import Any
{% for r in resources %}from ..api.{{ r.module }} import {{ r.cls }}
{% endfor %}{% if has_pagination %}from .pagination import paginate
{% endif %}
{% for r in resources %}
class {{ r.attr | classname }}Resource:
    def __init__(self, api: {{ r.cls }}) -> None:
        self._api = api
{% for m in r.methods %}
{% if m.kind == "list" %}
    def list(self{{ m.params | sig }}, *, all_pages: bool = False) -> {{ m.return_model }}:
        if all_pages:
            items = list(paginate(self._api.{{ m.raw_method }}{{ m.params | call }}))
            return {{ m.return_model }}(data=items, total=len(items), offset=0, limit=len(items))
        return self._api.{{ m.raw_method }}({{ m.params | call_kw }})
{% elif m.kind == "get" %}
    def get(self{{ m.get_params | sig_optional }}) -> {{ m.return_model }}:
        present = {k for k, v in locals().items() if k != "self" and v is not None}
{% for b in m.get_bindings %}        if {{ b.requires | present_check }}:
            return self._api.{{ b.raw_method }}({{ b.requires | call_kw }}){{ b.unwrap }}
{% endfor %}        raise ValueError("get() requires one of: {{ m.get_bindings | requires_help }}")
{% else %}
    def {{ m.name }}(self{{ m.params | sig }}{% if m.body_param %}, body: {{ m.body_model }}{% endif %}) -> {{ m.return_model }}:
        return self._api.{{ m.raw_method }}({{ m.params | call_kw }}{% if m.body_param %}, {{ m.body_param }}=body{% endif %})
{% endif %}
{% endfor %}
    def _serialize(self, verb: str, **kwargs: Any) -> tuple:
        """CLI-only dry-run seam: returns (method, url, headers, body, auth) without sending."""
        raw = {{ '{' }}{% for m in r.methods %}"{{ m.name }}": "{{ m.serialize_name }}",{% endfor %}{{ '}' }}[verb]
        fn = getattr(self._api, raw)
        params = {k: (0 if k == "_host_index" else None) for k in _sig_params(fn)}
        params.update(kwargs)
        return fn(**params)
{% endfor %}

def _sig_params(fn: Any) -> list[str]:
    import inspect
    return list(inspect.signature(fn).parameters)
```
> The `| sig`, `| call_kw`, `| present_check`, `| unwrap` filters are small Jinja
> filters registered in `render.py`; implement them in Step 2 (they turn
> `ParamView`s into Python signature/call fragments and the GET-unwrap `.data[0]`
> for ops whose serialize op returns an envelope). Keep the rendered code
> `ruff`-clean (the gate runs `ruff format --check` on the generator, not the
> artifact, but the smoke import must succeed).

- [ ] **Step 2: Register the resource component in `render.py::vendor`**

Add a `write_component`-style call that renders `resource.py.jinja` →
`extras/resources.py` using `build_wrapper_context(...)` for `resources=`, and
register the Jinja filters (`sig`, `call_kw`, etc.). Mirror how the facade
component is vendored (`_discover_resources` + `write_component`).

- [ ] **Step 3: Test — emitted resources.py imports and has clean methods**

```python
# tests/test_render.py (extend)
def test_resource_wrapper_emitted(tmp_path, vendor_fixture):
    pkg = vendor_fixture(...)  # existing render fixture
    src = (pkg / "extras" / "resources.py").read_text()
    assert "class DeviceGroupsResource" in src or "class DeviceGroupResource" in src
    assert "def create(self" in src and "def get(self" in src and "def list(self" in src
    assert "all_pages: bool = False" in src
    assert "_create_device_group" not in src.split("def _serialize")[0]  # raw name only in seam
```

- [ ] **Step 4: Run + gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_render.py -v`
Expected: PASS. Then `uv run nox -s gate`.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/sdk/components/facade/resource.py.jinja src/phantasos/generator/sdk/render.py tests/test_render.py
git commit -m "feat(sdk): typed resource-wrapper template + private _serialize seam"
```

### Task 3.3 — Facade binds wrappers; keep `_RESOURCES`

**Files:**
- Modify: `src/phantasos/generator/sdk/components/facade/client.py.jinja`
- Test: `tests/test_render.py`

- [ ] **Step 1: Edit the facade template — bind wrappers, keep raw map**

```jinja
{% for r in resources %}from .resources import {{ r.attr | classname }}Resource
{% endfor %}
_RESOURCES = {          # raw *Api map — retained for introspection contract
{% for r in resources %}    "{{ r.attr }}": {{ r.cls }},
{% endfor %}}

class Client:
    def __init__(self, api_client):
        self._api_client = api_client
        ...
        for name, api_cls in _RESOURCES.items():
            setattr(self, name, _wrapper_for(name)(api_cls(api_client)))   # wrapper, not raw

    @property
    def api_client(self):           # the single capture point (D5)
        return self._api_client
```
Add a `_wrapper_for(name)` map `{attr: <Resource>Resource}` next to `_RESOURCES`.

- [ ] **Step 2: Test — client.<resource> is the wrapper, raw not exposed**

```python
def test_facade_binds_wrapper(vendor_fixture):
    pkg = vendor_fixture(...)
    facade = import_emitted(pkg, "extras.facade")
    client = facade.Client(FakeApiClient())
    assert type(client.device_groups).__name__.endswith("Resource")
    assert hasattr(client.device_groups, "create")
    assert not hasattr(client.device_groups, "create_device_group")  # raw hidden (D2/D8)
    assert "device_groups" in facade._RESOURCES                       # raw map retained
```

- [ ] **Step 3: Run + gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_render.py -v && uv run nox -s gate
git add src/phantasos/generator/sdk/components/facade/client.py.jinja tests/test_render.py
git commit -m "feat(sdk): facade binds client.<resource> to the typed wrapper; keep _RESOURCES"
```

### Task 3.4 — Wire wrapper-gen into `build.py`

**Files:**
- Modify: `src/phantasos/generator/sdk/build.py`
- Test: `tests/test_sdk_build.py` (or the existing build test)

- [ ] **Step 1: Add the sub-step after OAG, before facade vendor**

In `build()`, after OAG generation and patches, before/within `vendor()`:
introspect the just-built package (`opmodel.introspect.introspect(package,
out_dir)`), `build_wrapper_context(inv, loaded.config.operations)`, pass the
result into `vendor()` so the resource + facade templates receive `resources=`.

- [ ] **Step 2: Test — a full build emits resources.py and imports clean**

```python
def test_build_emits_resource_wrapper(tmp_path):
    result = build(load_product("prisma-browser"), run_smoke=True)
    assert result["smoke"]["failed"] == 0
    out = Path(load_product("prisma-browser").config.output)
    assert (out / "prisma_browser" / "extras" / "resources.py").exists()
```

- [ ] **Step 3: Real build both products — collision gate must stay quiet**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build prisma-browser
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build posture
```
Expected: both succeed. If a collision fails the build, add the disambiguating
`sdk.yml operations:` entry to that product and record it.

- [ ] **Step 4: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/sdk/build.py tests/test_sdk_build.py products/*/sdk.yml
git commit -m "feat(sdk): generate the resource wrapper during the SDK build (introspect→classify→render)"
```

---

## Task 4: Re-base the CLI onto the wrapper

### Task 4.1 — CLI introspects the wrapper; classify clean names

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py::build_cli_ir`,
  `src/phantasos/generator/cli/introspect.py` usage in `cli.py`/`render_cli.py`

**Interfaces:**
- `build_cli_ir` now receives an inventory introspected from the **wrappers** (the
  facade now binds wrappers, and introspection walks `_RESOURCES` whose classes are
  raw — so introspect the bound wrapper instances instead). Change the registry
  the CLI introspects to the wrapper classes via a new facade attribute
  `_WRAPPERS` (added in 3.3) and `registry_attr="_WRAPPERS"`.

- [ ] **Step 1: Add `_WRAPPERS` map to the facade (3.3 follow-up) and introspect it**

In `client.py.jinja` add `_WRAPPERS = {"<attr>": <Resource>Resource, ...}`.
In `cli.py`/`render_cli.py`, call `introspect(pkg, sdk_path, registry_attr="_WRAPPERS")`.

- [ ] **Step 2: `build_cli_ir` uses `classify_clean`; GET binding via .get**

In `build_cli_ir`, replace `classify_name(op.method)` with `classify_clean(op.method)`
(method names are now clean). The `.get` method introspects with multiple
`get_bindings` — emit them as the command's `bindings` (the `_pick_binding` data
is still per-command). `MethodBinding.sdk_method` becomes the clean method name
(`get`/`list`/`create`/…); for `.get` the runtime calls `client.<res>.get(**args)`
and the wrapper picks the underlying op (so the CLI binding is a single `get`).

- [ ] **Step 3: Test — IR built from wrappers reproduces the command keys**

```python
def test_cli_ir_from_wrapper_keys(REAL_SDK):
    inv = introspect("prisma_browser", REAL_SDK, registry_attr="_WRAPPERS")
    ir, unmapped = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    keys = {c.key for c in ir.commands}
    assert {"create:device-group", "show:device-group", "delete:device-group"} <= keys
    assert unmapped == []
```

- [ ] **Step 4: Run + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_emitted_real.py -v
git add src/phantasos/generator/cli tests
git commit -m "feat(cli): build the command IR by introspecting the wrapper (clean names)"
```

### Task 4.2 — Runtime: dispatch clean methods, dry-run via seam, capture facade, drop paginate

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja`

- [ ] **Step 1: Dispatch through the wrapper method**

`run()`: `api = getattr(client, cmd.sdk_resource)` (now the wrapper);
`method = getattr(api, binding.sdk_method)` (clean name). Drop the
`binding.sub_verb == "list" and paginate_all` branch's `client.paginate(...)`;
instead pass `all_pages=paginate_all` into a `list` call:
```python
if binding.sub_verb == "list":
    result = method(**kwargs, all_pages=paginate_all)
else:
    result = method(**kwargs)
```

- [ ] **Step 2: Dry-run via the seam**

`_dry_run()`: replace `getattr(api, f"_{binding.sdk_method}_serialize")` with
`api._serialize(binding.sdk_method, **kwargs)` (the wrapper owns the None-fill):
```python
def _dry_run(cmd, binding, kwargs):
    client = facade.Client(_credential_free_api_client())
    api = getattr(client, cmd.sdk_resource)
    method, url, _headers, body, *_ = api._serialize(binding.sdk_method, **kwargs)
    _output.render_dry_run(method, url, body)
```

- [ ] **Step 3: HTTP capture at the facade**

Replace `api_client = getattr(api, "api_client", None)` with
`api_client = getattr(client, "api_client", None)` (facade-level, D5).

- [ ] **Step 4: `_accepted_params` reads the wrapper method**

`getattr(facade._WRAPPERS[resource], sdk_method)` (clean method signature).

- [ ] **Step 5: Test — emitted CLI still produces identical command behaviour**

Run the existing emitted CliRunner suite:
`UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_emitted.py tests/test_cli_emitted_real.py -v`
Expected: PASS (same flags, output, exit codes).

- [ ] **Step 6: Dry-run parity check (manual evidence)**

```bash
# rebuild prisma-browser-cli, then:
prisma-browser-cli create device-group --name x --dry-run   # compare method+URL+body to pre-change
```
Record the before/after in the commit message; they must match.

- [ ] **Step 7: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja
git commit -m "feat(cli): runtime dispatches the wrapper; dry-run via _serialize seam; facade capture; all_pages"
```

---

## Task 5: Verification (the retain gates)

**Files:** none new (runs the oracles from Task 0).

- [ ] **Step 1: Rebuild both products + regenerate CLIs**

```bash
for p in prisma-browser posture; do
  UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build $p
  UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos cli build $p
done
```

- [ ] **Step 2: Golden diff — the retain oracle**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_discover_golden.py -v`
Expected: PASS. If it fails, inspect the diff: a *semantic* change (command path,
flag, column) is a regression to fix; a benign help-text shift gets the golden
re-captured + recorded in the PR.

- [ ] **Step 3: Full emitted suite + gate**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
```
Expected: all green.

- [ ] **Step 4: Live CRUD — prisma-browser only**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s live
```
Expected: prisma-browser CRUD round-trip passes (posture skips — no tenant).
Show the real output as evidence.

- [ ] **Step 5: Commit any product `sdk.yml operations` overrides needed**

```bash
git add products/*/sdk.yml
git commit -m "chore: product sdk.yml operations overrides for clean wrapper names (if any)"
```

---

## Task 6: Docs + changelog

**Files:**
- Modify: `.agents/context/{sdk-generator,cli-generator,components,product-config}.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update the context narratives**

Describe: the shared `generator/opmodel/`; the resource-wrapper component + the
`_serialize` seam; the facade binding `client.<resource>` to wrappers (raw
`_RESOURCES` retained); the CLI introspecting/dispatching the wrapper; `sdk.yml
operations:`; `list(all_pages=)`; the `.get` collapse.

- [ ] **Step 2: Refresh generated context blocks**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s context`
Then verify: `... uv run nox -s context -- --check` (must pass).

- [ ] **Step 3: CHANGELOG under `## [Unreleased]`**

```markdown
### Added
- Generated SDKs now expose a typed `client.<resource>.<verb>(...)` wrapper; the
  generated CLI dispatches through it. New `sdk.yml operations:` naming override.
### Changed
- `list(all_pages=…)` replaces the CLI-side pagination loop. Raw `*Api` is no
  longer reachable from the client object.
```

- [ ] **Step 4: Gate + commit + open PR**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add .agents/context CHANGELOG.md
git commit -m "docs: clean resource wrapper + CLI-on-wrapper; changelog"
gh pr create --base develop --title "CLI on the clean resource wrapper" --body "Implements docs/specs/2026-06-19-cli-on-clean-resource-wrapper-design.md"
```

---

## Peer review outcome — **NO-GO (2026-06-19, 2× python-pro, verified)**

Both adversarial reviews returned NO-GO; the central blockers were reproduced
against the real prisma-browser SDK. **This plan must not be executed as written;
the design needs revision first.** Confirmed blockers:

1. **Wrapper granularity (foundational).** `client.<resource>` keys by the OAG
   `*Api` class, but that is coarser than the CLI's classified objects: 5
   resources host multiple objects (`access_and_data_policy` → policy/rule/section;
   `applications` → application/application-category). The wrapper must key by
   **classified object**, not API class. Touches D1/D3/D9 + the facade contract.
2. **Multi-binding for ALL verbs, not just `.get`.** Within an object, get/list/
   delete/update each aggregate multiple ops; the flat "one method per op" premise
   fails the collision gate on prisma-browser. `.get`/`.list`/`.delete`/`.update`
   need `_pick_binding`-style dispatch in the wrapper. The collapse also breaks the
   CLI's default `bare show → list` ordering (collapsed `.get` has empty `requires`).
3. **`sdk.yml operations` keying unimplementable as specified.** `OperationInfo`
   has no operationId/path — D11's operationId key has no data source; the
   `resolve_overrides` key-set expression is a no-op bug. Re-key by SDK method name
   / `resource.method`.
4. **`cli.yml` keys are raw-method-shaped** → clean-name introspection breaks every
   key (build fails / hides+variants vanish). D11's "cli.yml independent" boundary
   doesn't hold mechanically; needs a key-migration decision.
5. **Pagination.** `all_pages=True` envelope synthesis is product-specific and
   drops fields on prisma-browser's cursor envelope (use `page.model_copy(update=
   {"data": items})`); dropping `client.paginate` loses the cli.yml sort/order
   injection cursor pagination requires (else `--all` truncates at 100).
6. **Dry-run seam** loses enum coercion + body-param translation; can't pick the
   right underlying op for a collapsed `.get`.
7. **Test oracle.** Golden `cli discover` prints raw method names → self-defeating;
   real-SDK tests mock raw names → can't "stay green." Need a stable projection +
   dispatch-matrix / dry-run-parity / multi-page tests.
8. **None-classified real ops** (`update_device_group` PUT, `bulk_*`,
   `suspend_devices`, `*_positions`, `publish_draft_configuration`) have no
   wrapper-gen path.

**Next:** re-grill the design (granularity, multi-binding, key scheme,
None-classified handling), revise the spec, then rewrite the affected tasks.

## Self-Review

- **Spec coverage:** D1 (single source) → T3.3/T4; D2 (mirror sig) → T3.1/3.2;
  D3 (flat methods, .get collapse, collision gate, sdk.yml override) → T2/T3.1/T3.4;
  D4 (Pure A `_serialize`) → T3.2/T4.2; D5 (facade capture) → T4.2; D6 (variants
  as-is) → unchanged `_build_body` (verified by T4 emitted tests); D7 (all_pages)
  → T3.2/T4.2; D8 (no escape hatch) → T3.3 test; D9 (pipeline/introspect wrapper)
  → T3.4/T4.1; D10 (verification) → T0/T5; D11 (config + opmodel) → T1/T2.
- **Placeholder scan:** Jinja filters in T3.2 are named but their bodies are
  described, not shown — flagged for the implementer to write against the
  `ParamView` shape from T3.1 (acceptable: they are small string-builders, fully
  determined by `ParamView`). All test code is concrete.
- **Type consistency:** `WrapperMethod`/`ResourceView`/`GetBinding` defined in
  T3.1, consumed in T3.2/T3.4; `_serialize(verb, **kwargs)` signature consistent
  across T3.2 (def) and T4.2 (call); `registry_attr` consistent across T1/T4.1.
</content>
