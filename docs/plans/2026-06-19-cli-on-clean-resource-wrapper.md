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

**Modified:** `cli/classify.py` (re-export + `build_cli_ir` reads `_bindings`); `cli/introspect.py` (shim); `components/facade/client.py.jinja` (two-pass, `_RESOURCES`+`_WRAPPERS`); `generator/sdk/render.py` (vendor resource template + two-pass facade); `generator/sdk/build.py` (introspect→classify→wrapper sub-step); `config.py` (`OperationOverride`); `templates/_generated/runtime.py.jinja` (dispatch/dry-run/capture/all_pages); `tests/test_cli_emitted_real.py` AND `tests/test_cli_emitted.py` (rewrite raw-name assertions — see Task 5.0); `tests/fixtures/fakesdk/**` (regenerate the wrapper surface — Task 5.0).

> **NO `Command` field rename.** `Command.sdk_resource` is KEPT (no `sdk_object` rename) to avoid touching every reader (`discover.py`, `render_cli.py`, `app.py.jinja`, `ir.py`, and the `Command(sdk_resource=…)` tests). Post-rewrite it semantically holds the **object** attribute (`client.<object>`), the dispatch target; readers are unchanged because the field name is unchanged. `render_cli.py` now groups one command-module per object (finer — fine); `app.py`'s `getattr(client, sdk_resource)` resolves the object wrapper.

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
def OBJECT_OF(method: str) -> str | None:
    """Object noun (kebab) for a CRUD-prefixed raw method, else None.

    ONLY handles classifiable (verb-prefixed) methods. For None-classified ops the
    object is NOT reliably derivable from the method alone (the verb phrase may be
    1+ tokens: `suspend`, `bulk_create`, `publish_draft`), so those are mapped to an
    existing CRUD object on the same api class in build_wrapper_context (Task 3.1),
    or fail the build demanding an sdk.yml operations entry. Never guess here.
    """
    for prefix, _, _ in _VERB_PREFIXES:
        if method.startswith(prefix):
            return _singularize(_strip_id_suffix(method[len(prefix):])).replace("_", "-")
    return None
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

def test_object_of_crud_only():
    assert OBJECT_OF("get_application_by_type_and_id") == "application"
    assert OBJECT_OF("delete_access_and_data_rule_by_id") == "access-and-data-rule"
    assert OBJECT_OF("suspend_devices") is None        # non-CRUD -> derived in wrapper-gen
    assert OBJECT_OF("update_device_group") is None     # PUT -> handled in wrapper-gen
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
  - `ObjectView{attr:str, classname:str, api_cls:str, api_module:str, api_attr:str, methods:list[MethodView], imports:set[tuple[str,str]]}` (`api_attr` = the backing `_RESOURCES` key, for facade pass-2 + `_WRAPPERS`)
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
    assert "bulk_create" in m                                     # bulk_create_applications -> application
    # RD: PUT -> replace + verb-phrase actions attach to the EXISTING CRUD object (no junk objects)
    assert "replace" in {x.name for x in views["device_group"].methods}      # update_device_group (PUT)
    assert "suspend" in {x.name for x in views["device"].methods}            # suspend_devices
    assert "revoke" in {x.name for x in views["user_request"].methods}       # revoke_user_request
    assert "update_device_group" not in views and "suspend_device" not in views  # NO junk objects

@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_none_classified_without_crud_anchor_fails():
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.generator.opmodel.inventory import OperationInfo, OperationInventory
    inv = OperationInventory(sdk_package="p", sdk_version="0",
        operations=[OperationInfo(resource="ops", method="publish_draft_configuration")])
    with pytest.raises(ValueError, match="maps to no CRUD object"):
        build_wrapper_context(inv, {}, [{"attr": "ops", "module": "api.ops_api", "cls": "OpsApi"}])

@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_collision_fails():
    from phantasos.generator.sdk.wrapper import _gate_collisions, ObjectView, MethodView
    ov = ObjectView(attr="x", classname="X", api_cls="A", api_module="a", api_attr="xs", methods=[
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
from ..opmodel.classify import classify_name, OBJECT_OF, detect_id_param, _strip_id_suffix
from ..opmodel.inventory import OperationInfo, OperationInventory, ParamInfo

_PUT_PREFIX = "update_"   # OAG names PUT full-replace as update_*; classify_name returns None for it

@dataclass(frozen=True)
class Binding:
    raw_method: str
    requires: tuple[str, ...]
    serialize_name: str
# ParamView/MethodView/ObjectView as in Interfaces (mutable dataclasses); ObjectView carries `api_attr`.

def _crud_objects_by_api(inv) -> dict[str, set[str]]:
    """Per api-class, the CRUD object attrs (snake) — anchors that non-CRUD ops attach to."""
    out: dict[str, set[str]] = {}
    for op in inv.operations:
        o = OBJECT_OF(op.method)                       # None for non-CRUD
        if o is not None:
            out.setdefault(op.resource, set()).add(o.replace("-", "_"))
    return out

def _resolve_object(op, crud_objs, ov) -> str:
    """Object attr (snake) for ANY op. Override wins; CRUD via OBJECT_OF; non-CRUD by
    longest-suffix match against a CRUD object on the SAME api class; else BUILD-FAIL."""
    if ov and ov.resource:
        return ov.resource.replace("-", "_")
    o = OBJECT_OF(op.method)
    if o is not None:
        return o.replace("-", "_")
    stem = _strip_id_suffix(op.method)
    for cobj in sorted(crud_objs.get(op.resource, ()), key=len, reverse=True):
        if stem.endswith("_" + cobj) or stem.endswith("_" + cobj + "s") \
                or stem.endswith("_" + cobj[:-1] + "ies" if cobj.endswith("y") else False):
            return cobj
    raise ValueError(
        f"None-classified op {op.resource}.{op.method!r} maps to no CRUD object on its api "
        f"class (candidates: {sorted(crud_objs.get(op.resource, ()))}). Add `sdk.yml "
        f"operations: {{'{op.resource}.{op.method}': {{resource: <object>, method: <verb>}}}}`."
    )

def _verb_phrase(method: str, obj_snake: str) -> str:
    """Clean method for a non-CRUD op. PUT `update_*` -> 'replace'; else strip the trailing
    object noun (and the `_by_id`/`_by_type_and_id` tail) from the method.
    suspend_devices/device -> 'suspend'; bulk_create_applications/application -> 'bulk_create';
    revoke_user_request/user_request -> 'revoke'; publish_draft_configuration/configuration ->
    'publish_draft'; update_security_section_by_id/security_section -> 'replace' (PUT)."""
    if method.startswith(_PUT_PREFIX):
        return "replace"
    stem = _strip_id_suffix(method)
    for tail in ("_" + obj_snake + "s", "_" + obj_snake,
                 ("_" + obj_snake[:-1] + "ies") if obj_snake.endswith("y") else "_\x00"):
        if stem.endswith(tail):
            return stem[: -len(tail)]
    return stem

def _clean_verb_and_method(op, overrides, crud_objs) -> tuple[str, str, str]:
    """Return (object_attr_snake, cli_verb, clean_method_name). NO KeyError: branch on verb."""
    ov = overrides.get(f"{op.resource}.{op.method}")
    obj = _resolve_object(op, crud_objs, ov)
    c = classify_name(op.method)
    if c is not None:
        verb = ov.verb if (ov and ov.verb) else c.verb
        base = {"get": "get", "list": "list"}[c.sub_verb] if verb == "show" else verb
        method = ov.method if (ov and ov.method) else base
        return obj, verb, method
    # None-classified (RD)
    method = ov.method if (ov and ov.method) else _verb_phrase(op.method, obj)
    verb = ov.verb if (ov and ov.verb) else "request"
    return obj, verb, method

def build_wrapper_context(inv, overrides, discovered) -> list:
    validate_override_keys(inv, overrides)
    by_attr = {d["attr"]: d for d in discovered}            # api attr -> {module, cls}
    crud_objs = _crud_objects_by_api(inv)
    objects: dict[str, ObjectView] = {}
    method_ops: dict[tuple[str, str], list[OperationInfo]] = {}
    obj_api: dict[str, str] = {}                            # object attr -> api resource attr
    obj_verb: dict[tuple[str, str], str] = {}
    for op in inv.operations:
        obj_attr, verb, method = _clean_verb_and_method(op, overrides, crud_objs)
        if obj_attr in obj_api and obj_api[obj_attr] != op.resource:
            raise ValueError(f"object '{obj_attr}' spans api classes "
                             f"{obj_api[obj_attr]} and {op.resource} — disambiguate via sdk.yml operations")
        obj_api[obj_attr] = op.resource
        method_ops.setdefault((obj_attr, method), []).append(op)
        obj_verb[(obj_attr, method)] = verb
    for (obj_attr, method), ops in method_ops.items():
        d = by_attr[obj_api[obj_attr]]
        ov = objects.setdefault(obj_attr, ObjectView(
            attr=obj_attr, classname=_classname(obj_attr), api_cls=d["cls"],
            api_module=d["module"], api_attr=obj_api[obj_attr], methods=[], imports=set()))
        ov.methods.append(_build_method(method, obj_verb[(obj_attr, method)], ops))
    _gate_collisions(list(objects.values()))
    return list(objects.values())
```
**`_build_method(method, verb, ops)`** — union the params across the method's `ops` into
`ParamView`s (each `optional=True`), one `Binding` per op (`requires` = required path-param
names sorted; `serialize_name=f"_{op.method}_serialize"`); `is_list = method=='list'`. Build
each `ParamView`'s `py_annotation`+`import_from` from the **LIVE introspected type** (NOT
`ParamInfo.annotation`, which is a debug repr like `<enum '...'>` / nested `Annotated`):

```python
import inspect, typing
def _render_annotation(live_type) -> tuple[str, tuple[str, str] | None]:
    """From a real type object -> (render-ready expr, import or None). Unwrap Annotated/Optional."""
    tp = live_type
    if typing.get_origin(tp) is typing.Annotated:           # Annotated[T, ...]
        tp = typing.get_args(tp)[0]
    optional = False
    if typing.get_origin(tp) in (typing.Union, __import__("types").UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        optional = len(args) < len(typing.get_args(tp))
        tp = args[0] if len(args) == 1 else tp
    if isinstance(tp, type) and tp.__module__.startswith(("prisma_browser", "<pkg>")):
        expr = tp.__qualname__ + (" | None" if optional else "")
        return expr, (tp.__module__.split(".", 1)[1], tp.__qualname__)   # ("models.x", "X")
    base = {str: "str", int: "int", bool: "bool", float: "float"}.get(tp, "str")
    return (base + " | None") if optional else base, None
```
Wrapper-gen already imports the SDK, so resolve live types via
`typing.get_type_hints(getattr(api_cls, raw_method), include_extras=False)` (keyed by the
raw param name) — the wrapper imports the model class, then `get_type_hints` on the EMITTED
wrapper resolves cleanly for the CLI/dry-run. Rename the body param to `body` (keep
`raw_name`); `return_model`/`return_import` from the op's return type the same way.

**`_to_raw(verb, kwargs)`** (emitted per object) — translate the wrapper call back to the raw
op's kwargs for dry-run/serialize: rename `body`→the selected op's raw body-param name;
rename `id`→the op's real path-param name (e.g. `device_group_id`); and coerce enum **strings
→ enum members** via the wrapper method's resolved annotations (the OAG `_serialize` twin does
`type.value` and raises `AttributeError` on a plain `str`). It uses the same `_select(verb,
present)` to know which op (hence which raw names/enums) applies.

**`_verb_phrase`/`_classname`/`_gate_collisions`** as above (`_classname`: snake→PascalCase;
`_gate_collisions`: raise `ValueError("…method name collision…")` on a duplicate method name
within one ObjectView).

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
{% if m.is_list %}        present = {{ m.present_expr }}
        return self._list("{{ m.name }}", present, all_pages, {{ m.call_dict }})
{% elif m.dispatch_lines %}{% for line in m.dispatch_lines %}        {{ line }}
{% endfor %}{% else %}        return self._api.{{ m.bindings[0].raw_method }}({{ m.call_single }})
{% endif %}
{% endfor %}
    def _select(self, verb: str, present: set[str] | None = None) -> dict[str, Any]:
        cands = [b for b in self._bindings[verb] if set(b["requires"]) <= (present or set())]
        if not cands:
            raise ValueError(f"{verb}: missing required arg(s)")
        return max(cands, key=lambda b: len(b["requires"]))

    def _list(self, verb: str, present: set[str], all_pages: bool, kwargs: dict) -> Any:
        b = self._select(verb, present)                  # multi-binding: type-present -> *_by_type
        fn = getattr(self._api, b["raw_method"])
        raw = self._to_raw(verb, kwargs, b)              # routes `type` to path vs query per chosen op
        page = fn(**raw)
        if not all_pages:
            return page
        items = list(paginate(fn, **raw))                # re-walks from page 1 (cheap; first call = captured page 1)
        return page.model_copy(update={"data": items})

    def _serialize(self, verb: str, **kwargs: Any) -> tuple:
        present = {k for k, v in kwargs.items() if v is not None}
        b = self._select(verb, present)
        fn = getattr(self._api, b["serialize_name"])
        raw = self._to_raw(verb, kwargs, b)
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

Add a helper `cli_operations(package, sdk_path)` that imports the facade, walks `_WRAPPERS`, and for each object emits per-binding records `{object, clean_method, verb, raw_method, requires, params(from wrapper method sig), body_param, body_model, body_wrapper, return_model}` by combining `inspect.signature(wrapper_method)` with the class `_bindings`. **Body metadata (D6 variants):** extract `body_param="body"`, `body_model`, and `body_wrapper` (the oneOf wrapper class, e.g. `CreateOrReplaceAppInput`) from the wrapper method's `body` `ParamView` — the runtime's variant injection + `_build_body` need `body_wrapper` to wrap the variant, else `create application custom` sends a bare `CustomApplicationInput`. `build_cli_ir` consumes these; cli.yml keys resolve via `api_resource.raw_method`.

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
api = getattr(client, cmd.sdk_resource)          # field KEPT (no rename); now holds the object attr
method = getattr(api, binding.sdk_method)         # clean name
if binding.sub_verb == "list":
    result = method(**kwargs, all_pages=paginate_all)
    # RETAIN today's --all JSON shape (array, not the envelope object): for list
    # verbs, json/yaml output renders the items, not the synthesized envelope.
    if paginate_all and output in ("json", "yaml"):
        result = getattr(result, cmd.items_field) if cmd.items_field else result
else:
    result = method(**kwargs)
```
Delete the `client.paginate(...)` composition (runtime.py:530-532). (Table rendering
already unwraps `items_field`, so it is unaffected; only json/yaml needed the unwrap.)

- [ ] **Step 2: `show` get-vs-list selection (RB) + get-only diagnostic**

`_pick_binding` is RETAINED for this selection and the get-only diagnostic
(`_SUBVERB_PRIORITY` stays with it). Select by the detected id-param name (NOT a
literal `"id"` — many objects use `device_group_id` etc.). Bare `show` (no id flag)
→ `.list`; id present → `.get`; a get-only object with no `--id` keeps today's clean
"has no list operation" diagnostic instead of raising `StopIteration`:
```python
if cmd.verb == "show":
    id_names = {f.param for f in cmd.path_params if f.kind == "id"}
    has_id = any(path.get(n) is not None for n in id_names)
    cands = [b for b in cmd.bindings if (b.sub_verb == "get") == has_id]
    if not cands:                       # get-only object, --id omitted
        if cmd.get_by_id_only:
            _diag.fail(f"'{cmd.verb} {cmd.object}' has no list operation", code=2,
                       hint=f"fetch one by id, e.g. '{cmd.verb} {cmd.object} --id <id>'")
        _diag.fail(f"no operation for '{cmd.key}' matches the given arguments", code=2)
    binding = cands[0]
else:
    binding = cmd.bindings[0]            # single-binding commands post-collapse
```
This preserves `test_show_id_only_reports_no_list_operation` (SystemExit code 2 +
"has no list operation").

- [ ] **Step 3: Dry-run via the wrapper seam**

```python
def _dry_run(cmd, binding, kwargs):
    client = facade.Client(_credential_free_api_client())
    api = getattr(client, cmd.sdk_resource)
    method, url, _h, body, *_ = api._serialize(binding.sdk_method, **kwargs)
    _output.render_dry_run(method, url, body)
```
(The wrapper `_serialize` does enum coercion + `body`→raw-name translation, per T3.2.)

- [ ] **Step 4: Capture at the facade; `_accepted_params` via `_WRAPPERS`**

`api_client = getattr(client, "api_client", None)` (facade). `_accepted_params`: `getattr(facade._WRAPPERS[object][0], sdk_method)` signature (wrapper method accepts `sort`/`order`/`all_pages` for list).

- [ ] **Step 5: Rewrite the `fakesdk` fixture + `test_cli_emitted.py` to the wrapper surface**

This runtime change makes the emitted CLI dispatch the wrapper, so the fixture and
the 149-test suite (which both encode the RAW `*Api` surface) MUST be updated in the
SAME task to keep the gate green — they are NOT "stay green". Two parts:

1. **Fixture** (`tests/fixtures/fakesdk/fakesdk/extras/`): add the wrapper surface so
   `introspect("fakesdk", …, registry_attr="_WRAPPERS")` works. Either run wrapper-gen
   over the fixture, or hand-author: `resources.py` with one `*Resource` per object
   (`widget`, `gizmo`, `thing`), each with clean methods + a `_bindings` `ClassVar`
   + `_serialize`; add `_WRAPPERS` to `facade.py`; make `paginate` envelope-aware.
   Keep `_RESOURCES` (raw) for back-compat.
2. **Suite + `_fake_client`** (`tests/test_cli_emitted.py`): rewrite every raw-surface
   assertion to the wrapper surface — `_fake_client` exposes `client.<object>` (singular)
   with clean methods recording calls; assertions like `calls[0][0] == "create_widget"`
   → the wrapper `create` was called with `body=`; `kw["create_gizmo_input"]` →
   `body=` is the wrapped variant; `sdk_method == "widgets.get_widget_by_id"` →
   `widget.get`. Keep behavioural intent; version the method-name assertions explicitly
   (recorded oracle change).

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run pytest tests/test_cli_emitted.py -v
```
Expected: PASS after the rewrite.

- [ ] **Step 6: Gate + commit**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup uv run nox -s gate
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/fixtures/fakesdk tests/test_cli_emitted.py
git commit -m "feat(cli): runtime dispatches object wrappers; show get-vs-list by --id; dry-run seam; facade capture; all_pages; rewrite fakesdk+emitted suite to wrapper surface"
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
    # show application --id X          -> get_application_by_id
    # show application --id X --type T -> get_application_by_type_and_id
    # show application (bare)          -> list_applications
    # show application --type T        -> list_applications_by_type   (list-by-type, NOT get)
    ...  # assert the raw op recorded by a fake *Api for each arg combo

def test_delete_dispatch(monkeypatch, emitted):
    # delete application --id X          -> delete_application_by_id
    # delete application --id X --type T -> delete_application_by_type_and_id
    ...  # cover EVERY multi-binding object/verb, not just show
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
- **Type consistency:** `ParamView`/`Binding`/`MethodView`/`ObjectView` defined in T3.1, consumed T3.2/T3.3/T3.4; `_bindings` literal (T3.2) ↔ `cli_operations`/`build_cli_ir` reader (T4.1). `Command.sdk_resource` field name is KEPT (no rename — see the top note); it now semantically holds the object attr, so all existing readers (`runtime`, `discover`, `render_cli`, `app.py`, tests) are unchanged.
- **Retain coverage:** the golden tree (T0) pins the static command surface; T5's dispatch-matrix pins runtime routing for EVERY multi-binding object/verb; dry-run-parity + `--all`-multipage pin the seams; the `fakesdk` fixture + `test_cli_emitted.py` are rewritten to the wrapper surface (T4.2 Steps 5–6), not assumed green.
</content>
