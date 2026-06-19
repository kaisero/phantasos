# CLI on the clean resource wrapper — Implementation Plan (R1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Give every generated SDK a typed `client.<object>.<verb>(...)` wrapper that is the single source of truth, and re-base the generated CLI to introspect and dispatch through that wrapper instead of the raw OpenAPI-Generator `*Api` classes.

**Architecture:** Wrapper-gen (stage 1) groups operations by **classified object** (not the `*Api` class), emits one typed wrapper class per object backed by a shared `*Api` instance, and carries a `_bindings` op-model that drives multi-binding dispatch. The facade renders in two passes (raw-only `_RESOURCES` for mid-build introspection, then the full facade with `_WRAPPERS`). The CLI (stage 2) reads `_bindings`, keys its IR by `resource.raw_method` (so `cli.yml` is unchanged), and dispatches clean methods; dry-run reads `_bindings` through a wrapper `_serialize` seam.

**Tech Stack:** Python 3.12+, pydantic v2, Jinja2, urllib3 SDKs, Typer+Rich CLIs, OpenAPI Generator 7.22.0 (wrapped), `uv`+`nox`, pytest.

**Reference spec:** `docs/specs/2026-06-19-cli-on-clean-resource-wrapper-design.md` — read it, **especially Revisions RA–RD** (they supersede the original D-items).

## Global Constraints

- Prefix every uv/nox command with `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup`; for venv-backed nox (`live`) also `NOX_ENVDIR=/tmp/phantasos-nox`.
- Offline gate green after every task: `uv run nox -s gate`.
- Generated artifact is disposable — never hand-edit `*-sdk/`.
- Frozen oracles (`.claude/harness.toml` `protected_globs`): live-CRUD template, `tests/acceptance/**`, `.claude/**`. Never edit to pass.
- No new runtime deps in SDKs beyond `urllib3`, `python-dateutil`, `pydantic`, `typing-extensions`.
- Branch `feature/sdk-cleanup` off `develop`; squash-merge; no version bump; `## [Unreleased]` in CHANGELOG.
- **Targets prisma-browser ONLY** (posture is NOT on this branch — only `__pycache__`; add it as a follow-up when it lands on develop). Only the **cursor** pagination component exists here.
- Key everything by `resource.raw_method`. `cli.yml` keys stay unchanged.

---

## File Structure

**New:** `src/phantasos/generator/opmodel/{__init__,classify,introspect,inventory}.py`; `src/phantasos/generator/sdk/wrapper.py`; `src/phantasos/generator/sdk/components/facade/resource.py.jinja`; `tests/{test_opmodel_classify,test_sdk_operations_override,test_sdk_wrapper,test_cli_discover_golden,test_cli_dispatch_matrix}.py`; `tests/golden/prisma-browser.tree.json`.

**Modified:** `cli/classify.py` (re-export + `build_cli_ir` reads `_bindings`); `cli/introspect.py` (shim); `components/facade/client.py.jinja` (two-pass, `_RESOURCES`+`_WRAPPERS`); `generator/sdk/render.py` (vendor resource template + two-pass facade); `generator/sdk/build.py` (introspect→classify→wrapper sub-step); `config.py` (`OperationOverride`); `templates/_generated/runtime.py.jinja` (dispatch/dry-run/capture/all_pages); `tests/test_cli_emitted_real.py` (rewrite raw-name assertions).

---

## Task 0: Golden retain oracle — a STABLE PROJECTION

The oracle must exclude raw `sdk_method` (which flips raw→clean by design). Snapshot a structured projection of the command tree.

**Files:** Create `tests/test_cli_discover_golden.py`, `tests/golden/prisma-browser.tree.json`.

**Interfaces:**
- Produces: `project_tree(ir) -> list[dict]` — per command `{key, verb, object, variant, action, typer_path, flags: sorted([{name,kind,required}]), columns: [header...]}`, EXCLUDING `sdk_resource`/`bindings`/`sdk_method`.

- [ ] **Step 1: Write the projection + golden capture test**

```python
# tests/test_cli_discover_golden.py
import json
from pathlib import Path
import pytest
from phantasos.generator.opmodel.introspect import introspect
from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import load_cli_config

REAL = Path(__file__).parent.parent / "prisma-browser-sdk"
GOLD = Path(__file__).parent / "golden" / "prisma-browser.tree.json"


def project_tree(ir) -> list[dict]:
    out = []
    for c in sorted(ir.commands, key=lambda c: c.key):
        out.append({
            "key": c.key, "verb": c.verb, "object": c.object,
            "variant": c.variant, "action": c.action,
            "flags": sorted(
                [{"name": f.name, "kind": f.kind, "required": f.required}
                 for f in (c.path_params + c.body_flags + c.query_flags)],
                key=lambda d: d["name"]),
            "columns": [col.header for col in c.columns],
        })
    return out


def _build_ir():
    inv = introspect("prisma_browser", REAL)            # raw-*Api today; _WRAPPERS after T4
    ir, _ = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    return ir


@pytest.mark.skipif(not REAL.exists(), reason="prisma-browser SDK not built")
def test_command_tree_matches_golden():
    assert project_tree(_build_ir()) == json.loads(GOLD.read_text())
```

- [ ] **Step 2: Capture the golden on the current (raw-`*Api`) CLI**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run python -c "
import json; from pathlib import Path
from tests.test_cli_discover_golden import project_tree, _build_ir
Path('tests/golden').mkdir(exist_ok=True)
Path('tests/golden/prisma-browser.tree.json').write_text(json.dumps(project_tree(_build_ir()), indent=2))
"
```

- [ ] **Step 3: Run — passes against today's CLI**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_discover_golden.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/golden tests/test_cli_discover_golden.py
git commit -m "test(cli): stable-projection command-tree golden oracle (excludes sdk_method)"
```

---

## Task 1: Promote the op-model to `generator/opmodel/`

**Files:** Create `opmodel/{__init__,classify,introspect,inventory}.py`; Modify `cli/{classify,introspect,inventory}.py` (shims). Test `tests/test_opmodel_classify.py`.

**Interfaces:**
- Produces: `opmodel.classify.classify_name(str) -> Classification | None` (unchanged); `opmodel.classify.OBJECT_OF(str) -> str` (the object noun for a raw method, reusing `_strip_id_suffix`+`_singularize`); `opmodel.introspect.introspect(package, sdk_path, *, registry_attr="_RESOURCES") -> OperationInventory`.

- [ ] **Step 1: Move modules, leave shims**

```bash
mkdir -p src/phantasos/generator/opmodel
git mv src/phantasos/generator/cli/inventory.py src/phantasos/generator/opmodel/inventory.py
git mv src/phantasos/generator/cli/introspect.py src/phantasos/generator/opmodel/introspect.py
```
Move the pure helpers (`classify_name`, `_strip_id_suffix`, `_singularize`, `detect_id_param`, `Classification`, `_VERB_PREFIXES`, `_SKIP_FRAGMENTS`) into `opmodel/classify.py`; `build_cli_ir` + CLI helpers stay in `cli/classify.py`. Create `opmodel/__init__.py` re-exporting the public names. Add shims: `cli/inventory.py` and `cli/introspect.py` do `from ..opmodel.<mod> import *` plus explicit re-exports for mypy; `cli/classify.py` imports the helpers from `..opmodel.classify`.

- [ ] **Step 2: Add `OBJECT_OF` + parameterise `introspect`**

```python
# opmodel/classify.py
def OBJECT_OF(method: str) -> str:
    """Object noun (kebab) for a raw method name, even when classify_name is None."""
    for prefix, _, _ in _VERB_PREFIXES:
        if method.startswith(prefix):
            return _singularize(_strip_id_suffix(method[len(prefix):])).replace("_", "-")
    # non-CRUD: strip nothing reliably — caller supplies via sdk.yml or verb-phrase rule
    return _singularize(method).replace("_", "-")
```
```python
# opmodel/introspect.py
def introspect(package: str, sdk_path: Path, *, registry_attr: str = "_RESOURCES") -> OperationInventory:
    added = str(sdk_path) not in sys.path
    if added: sys.path.insert(0, str(sdk_path))
    try: return _introspect(package, registry_attr)
    finally:
        if added and str(sdk_path) in sys.path: sys.path.remove(str(sdk_path))

def _introspect(package: str, registry_attr: str) -> OperationInventory:
    pkg = importlib.import_module(package)
    facade = importlib.import_module(f"{package}.extras.facade")
    resources: dict[str, type[Any]] = getattr(facade, registry_attr)
    ...  # body unchanged; iterate resources.items()
```

- [ ] **Step 3: Test**

```python
# tests/test_opmodel_classify.py
from phantasos.generator.opmodel.classify import classify_name, OBJECT_OF

def test_classify_unchanged():
    c = classify_name("create_applications")
    assert (c.verb, c.object) == ("create", "application")
    assert classify_name("suspend_devices") is None

def test_object_of_for_none_classified():
    assert OBJECT_OF("get_application_by_type_and_id") == "application"
    assert OBJECT_OF("delete_access_and_data_rule_by_id") == "access-and-data-rule"
```

- [ ] **Step 4: Gate (proves the move broke nothing) + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/opmodel src/phantasos/generator/cli tests/test_opmodel_classify.py
git commit -m "refactor(gen): promote op-model to generator/opmodel; add OBJECT_OF + registry_attr"
```

---

## Task 2: `sdk.yml operations:` override (keyed by `resource.method`)

**Files:** Modify `src/phantasos/config.py`; Create `src/phantasos/generator/sdk/wrapper.py`. Test `tests/test_sdk_operations_override.py`.

**Interfaces:**
- Produces: `config.OperationOverride{resource:str|None, method:str|None, verb:str|None}` (extra=forbid, frozen); `ProductConfig.operations: dict[str, OperationOverride]`; `wrapper.validate_override_keys(inv, overrides) -> None` raising on unknown `resource.method` keys.

- [ ] **Step 1: Failing test (correct key set, not the prior no-op bug)**

```python
# tests/test_sdk_operations_override.py
import pytest
from phantasos.config import OperationOverride
from phantasos.generator.sdk.wrapper import validate_override_keys
from phantasos.generator.opmodel.inventory import OperationInfo, OperationInventory

def _inv(*keys):
    ops = [OperationInfo(resource=k.split(".")[0], method=k.split(".")[1]) for k in keys]
    return OperationInventory(sdk_package="p", sdk_version="0", operations=ops)

def test_unknown_key_fails():
    with pytest.raises(ValueError, match="unknown operation key"):
        validate_override_keys(_inv("applications.list_applications"),
                               {"applications.nope": OperationOverride(method="x")})

def test_known_key_ok():
    validate_override_keys(_inv("applications.list_applications"),
                           {"applications.list_applications": OperationOverride(method="list")})
```

- [ ] **Step 2: Implement model + validator**

```python
# config.py
class OperationOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    resource: str | None = None
    method: str | None = None
    verb: Literal["create","update","delete","show","request"] | None = None
# ProductConfig: operations: dict[str, OperationOverride] = Field(default_factory=dict)
```
```python
# generator/sdk/wrapper.py
def validate_override_keys(inv, overrides) -> None:
    keys = {f"{op.resource}.{op.method}" for op in inv.operations}
    unknown = set(overrides) - keys
    if unknown:
        raise ValueError(f"sdk.yml operations: unknown operation key(s): {', '.join(sorted(unknown))}")
```

- [ ] **Step 3: Run + gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_sdk_operations_override.py -v && uv run nox -s gate
git add src/phantasos/config.py src/phantasos/generator/sdk/wrapper.py tests/test_sdk_operations_override.py
git commit -m "feat(sdk): sdk.yml operations override keyed by resource.method + validation"
```

---

## Task 3.1: Wrapper render context — object granularity, ParamView, `_bindings`, multi-binding

**Files:** Modify `src/phantasos/generator/sdk/wrapper.py`. Test `tests/test_sdk_wrapper.py`.

**Interfaces:**
- Consumes: `opmodel.introspect.introspect`, `opmodel.classify.{classify_name,OBJECT_OF,detect_id_param}`, `render._discover_resources(pkg_dir) -> list[{attr,module,cls}]`, `config.OperationOverride`.
- Produces dataclasses:
  - `ParamView{name:str, raw_name:str, py_annotation:str, import_from:tuple[str,str]|None, optional:bool, default_repr:str, location:str, is_enum:bool, enum_cls:str|None}`
  - `Binding{raw_method:str, requires:tuple[str,...], serialize_name:str}`
  - `MethodView{name:str, verb:str, params:list[ParamView], body:ParamView|None, return_model:str, return_import:tuple[str,str]|None, bindings:list[Binding], is_list:bool, get_unwrap:bool}`
  - `ObjectView{attr:str, classname:str, api_cls:str, api_module:str, methods:list[MethodView], imports:set[tuple[str,str]]}`
  - `build_wrapper_context(inv, overrides, discovered) -> list[ObjectView]`

- [ ] **Step 1: Failing test against the real SDK (object granularity + multi-binding + none-classified)**

```python
# tests/test_sdk_wrapper.py
from pathlib import Path
import pytest
from phantasos.generator.opmodel import introspect
from phantasos.generator.sdk.render import _discover_resources
from phantasos.generator.sdk.wrapper import build_wrapper_context

SDK = Path(__file__).parent.parent / "prisma-browser-sdk"
PKG = SDK / "prisma_browser"

@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_object_granularity_and_multibinding():
    inv = introspect("prisma_browser", SDK)
    views = {v.attr: v for v in build_wrapper_context(inv, {}, _discover_resources(PKG))}
    # RA: access_and_data_policy api class -> THREE object wrappers
    assert {"access_and_data_rule", "access_and_data_section", "access_and_data_policy"} <= set(views)
    # RB: application.get and .list and .delete are multi-binding
    app = views["application"]
    m = {x.name: x for x in app.methods}
    assert m["get"].bindings and len(m["get"].bindings) == 2      # by-id + by-type-and-id
    assert len(m["list"].bindings) == 2 and m["list"].is_list
    assert len(m["delete"].bindings) == 2
    # RD: PUT -> replace; action -> verb phrase
    dgs = {x.name for x in views["device_group"].methods}
    assert "replace" in dgs                                       # update_device_group (PUT)
    assert "suspend" in {x.name for x in views["device"].methods} # suspend_devices

@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_collision_fails():
    from phantasos.generator.sdk.wrapper import _gate_collisions, ObjectView, MethodView
    ov = ObjectView(attr="x", classname="X", api_cls="A", api_module="a", methods=[
        MethodView("get","show",[],None,"I",None,[],False,False),
        MethodView("get","show",[],None,"I",None,[],False,False)], imports=set())
    with pytest.raises(ValueError, match="method name collision"):
        _gate_collisions([ov])
```

- [ ] **Step 2: Run — fails (module missing)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_sdk_wrapper.py -v` → ImportError.

- [ ] **Step 3: Implement `build_wrapper_context`**

```python
# generator/sdk/wrapper.py  (excerpt — full impl)
from dataclasses import dataclass, field
from .._render_types import ...   # (use plain dataclasses below)
from ..opmodel.classify import classify_name, OBJECT_OF, detect_id_param
from ..opmodel.inventory import OperationInfo, OperationInventory, ParamInfo

_PUT_PREFIX = "update_"   # OAG names PUT full-replace as update_*; classify_name returns None for it

@dataclass(frozen=True)
class Binding:
    raw_method: str
    requires: tuple[str, ...]
    serialize_name: str
# ParamView/MethodView/ObjectView as in Interfaces (mutable dataclasses)

def _clean_verb_and_method(op, overrides) -> tuple[str, str, str]:
    """Return (object_attr_snake, verb, clean_method_name)."""
    key = f"{op.resource}.{op.method}"
    ov = overrides.get(key)
    c = classify_name(op.method)
    if c is not None:
        obj = (ov.object if ov and getattr(ov, 'object', None) else c.object)
        verb = (ov.verb if ov and ov.verb else c.verb)
        method = {"create":"create","update":"update","delete":"delete",
                  "show":{"get":"get","list":"list"}[c.sub_verb]}[verb]
        return obj.replace("-","_"), verb, (ov.method if ov and ov.method else method)
    # None-classified (RD): PUT -> replace; else verb-phrase (strip object noun)
    obj = OBJECT_OF(op.method).replace("-","_") if not (ov and ov.resource) else ov.resource.replace("-","_")
    if op.method.startswith(_PUT_PREFIX):
        method = "replace"
    else:
        # strip the object noun tokens from the method to get the verb phrase
        method = _verb_phrase(op.method, OBJECT_OF(op.method))
    if ov and ov.method: method = ov.method
    if ov and ov.resource: obj = ov.resource.replace("-","_")
    return obj, "request", method

def build_wrapper_context(inv, overrides, discovered) -> list:
    validate_override_keys(inv, overrides)
    by_attr_module = {d["attr"]: d for d in discovered}     # attr -> {module, cls}
    objects: dict[str, ObjectView] = {}
    # group ops -> (object_attr, verb, method) ; bindings accumulate per (object, method)
    method_ops: dict[tuple[str,str], list[tuple[OperationInfo,str]]] = {}
    obj_api: dict[str, str] = {}                             # object_attr -> api resource attr
    for op in inv.operations:
        obj_attr, verb, method = _clean_verb_and_method(op, overrides)
        if obj_attr in obj_api and obj_api[obj_attr] != op.resource:
            raise ValueError(f"object '{obj_attr}' spans api classes "
                             f"{obj_api[obj_attr]} and {op.resource} — disambiguate via sdk.yml operations")
        obj_api[obj_attr] = op.resource
        method_ops.setdefault((obj_attr, method), []).append((op, verb))
    for (obj_attr, method), ops in method_ops.items():
        api_attr = obj_api[obj_attr]
        d = by_attr_module[api_attr]
        ov = objects.setdefault(obj_attr, ObjectView(
            attr=obj_attr, classname=_classname(obj_attr), api_cls=d["cls"],
            api_module=d["module"], methods=[], imports=set()))
        ov.methods.append(_build_method(obj_attr, method, ops))
    _gate_collisions(list(objects.values()))
    return list(objects.values())
```
Implement `_build_method` (union params across the method's ops into `ParamView`s — each `optional=True`; build `Binding` per op with `requires` = required path-param names sorted, `serialize_name=f"_{op.method}_serialize"`; `is_list = method=='list'`; render-ready `py_annotation` + `import_from` from `ParamInfo.annotation` via a small `_render_annotation(ParamInfo) -> (expr, import_or_None)` that maps `Optional[X]`→`X | None`, strips module path to the class name, and returns `(module, ClassName)` for model imports; body param renamed to `body`, `raw_name` kept; `return_model`+`return_import` from the op's `return_model`). Implement `_verb_phrase`, `_classname` (snake→PascalCase), `_gate_collisions` (raise on duplicate method name within an ObjectView).

- [ ] **Step 4: Run the test — passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_sdk_wrapper.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/sdk/wrapper.py tests/test_sdk_wrapper.py
git commit -m "feat(sdk): object-granular wrapper context (multi-binding, ParamView, _bindings, none-classified, collision gate)"
```

---

## Task 3.2: Resource-wrapper template (precomputed strings, `_bindings`, `_serialize`, `all_pages`)

**Files:** Create `components/facade/resource.py.jinja`; Modify `render.py` (vendor it). Test `tests/test_render.py`.

The template interpolates ONLY precomputed strings from `MethodView`/`ParamView` (no Jinja filters, no `locals()`).

- [ ] **Step 1: Write the template**

```jinja
"""Typed resource wrappers (vendored by phantasos)."""
from __future__ import annotations
import inspect
from typing import Any, ClassVar
{% for imp in imports %}from ..{{ imp[0] }} import {{ imp[1] }}
{% endfor %}{% if has_pagination %}from .pagination import paginate
{% endif %}
{% for o in objects %}
class {{ o.classname }}Resource:
    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {{ o.bindings_literal }}

    def __init__(self, api: {{ o.api_cls }}) -> None:
        self._api = api
{% for m in o.methods %}
    def {{ m.name }}(self, {{ m.sig }}) -> {{ m.return_expr }}:
{% if m.is_list %}        page = self._api.{{ m.bindings[0].raw_method }}({{ m.call_first }})
        if not all_pages:
            return page
        items = list(paginate(self._api.{{ m.bindings[0].raw_method }}, {{ m.call_kw }}))
        return page.model_copy(update={"data": items})
{% else %}        b = self._select("{{ m.name }}")
{% for line in m.dispatch_lines %}        {{ line }}
{% endfor %}{% endif %}
{% endfor %}
    def _select(self, verb: str, present: set[str] | None = None) -> dict[str, Any]:
        cands = [b for b in self._bindings[verb] if set(b["requires"]) <= (present or set())]
        if not cands:
            raise ValueError(f"{verb}: missing required arg(s)")
        return max(cands, key=lambda b: len(b["requires"]))

    def _serialize(self, verb: str, **kwargs: Any) -> tuple:
        present = {k for k, v in kwargs.items() if v is not None}
        b = self._select(verb, present)
        fn = getattr(self._api, b["serialize_name"])
        raw = self._to_raw(verb, kwargs)
        params = {k: (0 if k == "_host_index" else None) for k in inspect.signature(fn).parameters}
        params.update(raw)
        return fn(**params)
{% endfor %}
```
The Python side (Task 3.1) precomputes per `MethodView`: `sig` (e.g. `"id: str | None = None, *, all_pages: bool = False"` for list; all params optional), `return_expr`, `call_first`/`call_kw`, `bindings_literal` (a `repr`-able dict literal of `_bindings`), and `dispatch_lines` for non-list multi-binding methods, e.g.:
```python
# dispatch_lines for application.get:
['if id is not None and type is not None:',
 '    return self._api.get_application_by_type_and_id(id=id, type=type)',
 'if id is not None:',
 '    return self._api.get_application_by_id(id=id)',
 'raise ValueError("get: missing required arg(s)")']
```
For a by-query single-fetch binding whose op returns a list envelope, the generated lines unwrap-and-assert:
```python
['page = self._api.list_addresses(name=name)',
 'items = page.data or []',
 'if len(items) != 1:',
 '    raise ValueError(f"get: expected exactly one match, got {len(items)}")',
 'return items[0]']
```
(No prisma-browser get returns a list envelope today; this path is exercised by a synthetic-SDK test in T5, not the golden.) Also emit `_to_raw(verb, kwargs)` per object: rename `body`→the op's raw body param and coerce enum strings via the wrapper method's `__annotations__` (the typed sig), so dry-run matches the real call.

- [ ] **Step 2: Vendor it in `render.py`**

Add a `write_component` call rendering `resource.py.jinja` → `extras/resources.py` with `objects=build_wrapper_context(...)`, `imports=` the merged import set, `has_pagination=`. Register no filters.

- [ ] **Step 3: Test the emitted module imports + shape**

```python
# tests/test_render.py (extend)
def test_resources_emitted(vendor_fixture):
    pkg = vendor_fixture(...)
    src = (pkg / "extras" / "resources.py").read_text()
    assert "class ApplicationResource" in src
    assert "_bindings: ClassVar" in src and "def _serialize(self" in src
    assert "all_pages: bool = False" in src and "model_copy(update=" in src
    # raw method names appear ONLY in _bindings / dispatch bodies, never as public defs
    assert "def get_application_by_id" not in src
    import ast; ast.parse(src)   # parses clean
```

- [ ] **Step 4: Run + gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_render.py -v && uv run nox -s gate
git add src/phantasos/generator/sdk/components/facade/resource.py.jinja src/phantasos/generator/sdk/render.py tests/test_render.py
git commit -m "feat(sdk): resource-wrapper template (_bindings, multi-binding dispatch, all_pages via model_copy, _serialize seam)"
```

---

## Task 3.3: Facade — two-pass render (`_RESOURCES` then `_WRAPPERS`)

**Files:** Modify `components/facade/client.py.jinja`, `render.py`. Test `tests/test_render.py`.

- [ ] **Step 1: Template supports both passes via a flag**

```jinja
_RESOURCES = {
{% for r in resources %}    "{{ r.attr }}": {{ r.cls }},
{% endfor %}}
{% if wrappers %}
{% for o in objects %}from .resources import {{ o.classname }}Resource
{% endfor %}
_WRAPPERS = {
{% for o in objects %}    "{{ o.attr }}": ({{ o.classname }}Resource, "{{ o.api_attr }}"),
{% endfor %}}
{% endif %}
class Client:
    def __init__(self, api_client):
        self._api_client = api_client
        _apis = {name: cls(api_client) for name, cls in _RESOURCES.items()}
{% if wrappers %}        for obj, (wcls, api_attr) in _WRAPPERS.items():
            setattr(self, obj, wcls(_apis[api_attr]))   # shared *Api instance
{% endif %}
    @property
    def api_client(self):                              # single capture point (D5/RA)
        return self._api_client
```

- [ ] **Step 2: `render.py` renders the facade twice**

Pass 1 (`wrappers=False`) before introspection so the SDK imports; Pass 2 (`wrappers=True`, with `objects=`) after wrapper-gen. (Build wiring in T3.4.)

- [ ] **Step 3: Test — wrapper bound, raw hidden, both maps present**

```python
def test_facade_binds_object_wrappers(vendor_fixture):
    pkg = vendor_fixture(...)            # full build via T3.4
    facade = import_emitted(pkg, "extras.facade")
    client = facade.Client(FakeApiClient())
    assert type(client.application).__name__ == "ApplicationResource"
    assert client.access_and_data_rule._api is client.access_and_data_section._api  # shared *Api
    assert not hasattr(client.application, "get_application_by_id")
    assert "applications" in facade._RESOURCES and "application" in facade._WRAPPERS
```

- [ ] **Step 4: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/sdk/components/facade/client.py.jinja src/phantasos/generator/sdk/render.py tests/test_render.py
git commit -m "feat(sdk): two-pass facade — _RESOURCES (raw) + _WRAPPERS (object); shared *Api instances"
```

---

## Task 3.4: Wire wrapper-gen into `build.py`

**Files:** Modify `generator/sdk/build.py`. Test `tests/test_sdk_build.py`.

- [ ] **Step 1: Ordering — facade pass1 → introspect → wrapper-gen → resources + facade pass2**

In `build()` after OAG+patches: render facade pass1 (`_RESOURCES` only) → `inv = introspect(package, out_dir)` → `objects = build_wrapper_context(inv, loaded.config.operations, _discover_resources(pkg_dir))` → vendor `resources.py` + facade pass2(`wrappers=True, objects=objects`).

- [ ] **Step 2: Test full build emits resources + imports clean**

```python
def test_build_emits_wrapper():
    res = build(load_product("prisma-browser"), run_smoke=True)
    assert res["smoke"]["failed"] == 0
    out = Path(load_product("prisma-browser").config.output) / "prisma_browser"
    assert (out / "extras" / "resources.py").exists()
```

- [ ] **Step 3: Real build (collision gate must stay quiet)**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build prisma-browser
```
If a collision/cross-api error fires, add a `sdk.yml operations` entry to `products/prisma-browser/sdk.yml` and re-run; record it in the commit.

- [ ] **Step 4: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/sdk/build.py tests/test_sdk_build.py products/prisma-browser/sdk.yml
git commit -m "feat(sdk): generate object wrappers during the build (facade pass1 -> introspect -> wrapper-gen -> pass2)"
```

---

## Task 4.1: CLI builds its IR from `_WRAPPERS` + `_bindings`, keyed by `resource.raw_method`

**Files:** Modify `cli/classify.py::build_cli_ir`, the introspection call sites (`cli.py`, `render_cli.py`).

**Interfaces:**
- `build_cli_ir` iterates each wrapper's `_bindings`; for each binding it has `(object, clean_method, raw_method, requires)`. It keys cli.yml lookups by `f"{api_resource}.{raw_method}"` (UNCHANGED keys), groups into commands by classified verb/object, and sets `MethodBinding.sdk_method = clean_method`, `requires` from the binding. The `show` get-vs-list selection is left to the runtime (T4.2).

- [ ] **Step 1: Introspect `_WRAPPERS`; read `_bindings`**

Add a helper `cli_operations(package, sdk_path)` that imports the facade, walks `_WRAPPERS`, and for each object emits per-binding records `{object, clean_method, verb, raw_method, requires, params(from wrapper method sig), body_model, return_model}` by combining `inspect.signature(wrapper_method)` with the class `_bindings`. `build_cli_ir` consumes these; cli.yml keys resolve via `api_resource.raw_method`.

- [ ] **Step 2: Test — IR keys/commands reproduce the golden, cli.yml still applies**

```python
def test_ir_from_wrappers_no_unmapped(REAL_SDK):
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    inv = cli_operations("prisma_browser", REAL_SDK)
    ir, unmapped = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    keys = {c.key for c in ir.commands}
    assert {"create:device-group","show:device-group","delete:device-group"} <= keys
    assert "show:access-and-data-rule" in keys and "show:access-and-data-section" in keys  # RA
    assert unmapped == []                               # request/hide keyed by raw method still resolve
```

- [ ] **Step 3: Golden tree still matches (now via wrappers)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_discover_golden.py -v`
(Update `_build_ir` in the golden test to use `cli_operations(..._WRAPPERS)`.) Expected: PASS — the projection is unchanged.

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/generator/cli tests/test_cli_discover_golden.py
git commit -m "feat(cli): build IR from _WRAPPERS/_bindings; key by resource.raw_method (cli.yml unchanged)"
```

---

## Task 4.2: Runtime — dispatch clean methods, dry-run seam, facade capture, `all_pages`, `show` get-vs-list

**Files:** Modify `templates/_generated/runtime.py.jinja`.

- [ ] **Step 1: Dispatch through the wrapper; list via `all_pages`**

```python
api = getattr(client, cmd.sdk_object)            # the object wrapper (was sdk_resource)
method = getattr(api, binding.sdk_method)         # clean name
if binding.sub_verb == "list":
    result = method(**kwargs, all_pages=paginate_all)
else:
    result = method(**kwargs)
```
Delete the `client.paginate(...)` composition (runtime.py:530-532).

- [ ] **Step 2: `show` get-vs-list selection (RB)**

In `run()` binding selection: for a `show` command with both `.get` and `.list` bindings, choose `.get` iff `--id` is present, else `.list`:
```python
if cmd.verb == "show":
    has_id = path.get("id") is not None
    binding = next(b for b in cmd.bindings if (b.sub_verb == "get") == has_id)
else:
    binding = cmd.bindings[0]            # single-binding commands post-collapse
```

- [ ] **Step 3: Dry-run via the wrapper seam**

```python
def _dry_run(cmd, binding, kwargs):
    client = facade.Client(_credential_free_api_client())
    api = getattr(client, cmd.sdk_object)
    method, url, _h, body, *_ = api._serialize(binding.sdk_method, **kwargs)
    _output.render_dry_run(method, url, body)
```
(The wrapper `_serialize` does enum coercion + `body`→raw-name translation, per T3.2.)

- [ ] **Step 4: Capture at the facade; `_accepted_params` via `_WRAPPERS`**

`api_client = getattr(client, "api_client", None)` (facade). `_accepted_params`: `getattr(facade._WRAPPERS[object][0], sdk_method)` signature (wrapper method accepts `sort`/`order`/`all_pages` for list).

- [ ] **Step 5: Run emitted suites**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_emitted.py -v
```
Expected: PASS (the raw-name-asserting `test_cli_emitted_real.py` is rewritten in T5).

- [ ] **Step 6: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja
git commit -m "feat(cli): runtime dispatches object wrappers; show get-vs-list by --id; dry-run seam; facade capture; all_pages"
```

---

## Task 5: Verification + retain tests (the gates D10 / reviewer-mandated)

**Files:** Modify `tests/test_cli_emitted_real.py`; Create `tests/test_cli_dispatch_matrix.py`.

- [ ] **Step 1: Rewrite `test_cli_emitted_real.py` raw-name assertions (recorded oracle change)**

Enumerate and rewrite each assertion that mocks/asserts a raw method (`get_application_by_type_and_id`, `device_group_request`, `create_or_replace_app_input`, `patch_device_group`) to the wrapper surface: mock `client.<object>.<clean_method>` and assert the wrapper was called with `body=`/`id=`/`type=`. Record the before/after in the commit body.

- [ ] **Step 2: Dispatch-matrix retain test (golden can't cover this)**

```python
# tests/test_cli_dispatch_matrix.py — fake client records which raw op fires
def test_show_dispatch(monkeypatch, emitted):
    # show application --id X        -> get_application_by_id
    # show application --id X --type T -> get_application_by_type_and_id
    # show application (bare)         -> list_applications
    # show application --type T       -> list_applications_by_type
    ...  # assert the raw op recorded by a fake *Api for each arg combo
```

- [ ] **Step 3: Dry-run parity + `--all` multi-page tests**

```python
def test_dry_run_parity(emitted):
    out = run_cli("create device-group --name x --dry-run")
    assert "POST" in out and "/device-groups" in out and '"name": "x"' in out

def test_all_pages_walks_and_injects_sort(fake_multipage):
    out_urls = run_cli_capture("show application --all")
    assert "sort=application.name" in out_urls[0] and "order=asc" in out_urls[0]  # cli.yml default
    assert len(out_urls) >= 2                                                     # page 2 fetched
    # history records page 1
    assert history_last()["http_uri"].endswith("/applications")
```

- [ ] **Step 4: Rebuild + regenerate + full gate + live**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos sdk build prisma-browser
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run phantasos cli build prisma-browser
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s live   # prisma-browser only
```
Show the live output as evidence.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli_emitted_real.py tests/test_cli_dispatch_matrix.py
git commit -m "test(cli): rewrite raw-name oracles to wrapper surface; add dispatch-matrix, dry-run-parity, --all multipage retain tests"
```

---

## Task 6: Docs + changelog

**Files:** Modify `.agents/context/{sdk-generator,cli-generator,components,product-config}.md`, `CHANGELOG.md`.

- [ ] **Step 1: Update narratives** — `generator/opmodel/`; object-granular resource wrapper + `_bindings`; two-pass facade (`_RESOURCES`+`_WRAPPERS`); CLI reads `_bindings`, keys by `resource.raw_method`; `sdk.yml operations`; `list(all_pages=)`; `show` get-vs-list.
- [ ] **Step 2:** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-ctx uv run nox -s context` then `... nox -s context -- --check`.
- [ ] **Step 3:** CHANGELOG `## [Unreleased]`:
```markdown
### Added
- Typed `client.<object>.<verb>(...)` resource wrappers; the generated CLI now
  dispatches through them. `sdk.yml operations:` naming override.
### Changed
- `list(all_pages=…)` replaces the CLI pagination loop. Raw `*Api` no longer
  reachable from the client.
```
- [ ] **Step 4:** Gate + commit + `gh pr create --base develop`.

---

## Self-Review

- **Spec coverage:** RA → T3.1/T3.3 (object grouping, `_WRAPPERS`, shared api, cross-api gate); RB → T3.1/T3.2 (`_bindings`, dispatch chains) + T4.2 Step 2 (show get-vs-list); RC → T2 (key set fix) + T3.1/T3.2 (`_bindings`) + T4.1 (`resource.raw_method`, cli.yml unchanged); RD → T3.1 (`replace`/verb-phrase) + T2 override. Plan-level fixes: envelope `model_copy` (T3.2), dry-run coercion/translation (T3.2/T4.2), stable-projection oracle (T0), two-pass facade (T3.3), real-SDK test rewrite + dispatch-matrix/dry-run/all-pages tests (T5). D5 capture → T4.2 Step 4.
- **Placeholder scan:** the `_render_annotation`, `_to_raw`, `_verb_phrase`, `dispatch_lines` builders are specified by inputs/outputs with worked examples (not "TBD"); all test code is concrete. No "similar to Task N".
- **Type consistency:** `ParamView`/`Binding`/`MethodView`/`ObjectView` defined in T3.1, consumed T3.2/T3.3/T3.4; `_bindings` literal (T3.2) ↔ `cli_operations`/`build_cli_ir` reader (T4.1); `sdk_object` used consistently T4.1/T4.2 (rename from `sdk_resource` — update `Command` field accordingly in T4.1).
</content>
