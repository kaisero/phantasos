# CLI Generator — Phase 1: Generator Core + Discover — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the introspection → classification → `CliIR` core of the phantasos CLI generator, plus the `phantasos cli discover <product>` command that prints a classification table and writes a `cli.yml` stub. No code emission yet (Phase 2).

**Architecture:** An IR-centric pipeline under `src/phantasos/generator/cli/`. `introspect.py` imports a built SDK and produces a typed `OperationInventory`. `classify.py` applies deterministic rules + per-product `cli.yml` deltas to produce a typed `CliIR` (the resolved command tree). `discover.py` renders both a human table and a `cli.yml` stub from the same `CliIR`. This mirrors phantasos's existing `productconfig → render` typed-model pattern. The top-level `src/phantasos/cli.py` gains a `cli discover` subcommand that delegates into the new package.

**Tech Stack:** Python 3.11+, Pydantic v2 (already a dependency), `inspect` + `typing.get_type_hints`, pytest. Test runner: `uv run pytest` (recreates the venv from `uv.lock`).

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md`. **Reference for types:** `src/phantasos/productconfig.py`.

---

## Environment note

The repo's `.venv` may be stale. Before running any test, ensure deps are synced once:

```bash
uv sync --all-groups
```

All test/commit commands below assume the repo root `/home/ubuntu/git/phantasos` and branch `cli-generator` (already created).

---

## File structure (created in this phase)

- Create: `src/phantasos/generator/__init__.py` — namespace package marker.
- Create: `src/phantasos/generator/cli/__init__.py` — generator subpackage marker.
- Create: `src/phantasos/generator/cli/ir.py` — `Flag`, `Command`, `CliIR` (the rendered/reported artifact).
- Create: `src/phantasos/generator/cli/cliconfig.py` — `CliConfig` (the `cli.yml` deltas model) + `load_cli_config`.
- Create: `src/phantasos/generator/cli/inventory.py` — `ParamInfo`, `FieldInfo`, `OperationInfo`, `OperationInventory` (introspection output).
- Create: `src/phantasos/generator/cli/introspect.py` — `introspect(package, sdk_path)` → `OperationInventory`.
- Create: `src/phantasos/generator/cli/classify.py` — classification helpers + `build_cli_ir(inventory, config)` → `CliIR`.
- Create: `src/phantasos/generator/cli/discover.py` — `render_table(ir, unmapped)`, `render_stub(ir, unmapped)`.
- Modify: `src/phantasos/cli.py` — add `cli discover` subcommand.
- Create (test fixture): `tests/fixtures/fakesdk/fakesdk/{__init__,models,api}.py` + `tests/fixtures/fakesdk/fakesdk/extras/facade.py`.
- Create (tests): `tests/test_cli_ir.py`, `tests/test_cli_config.py`, `tests/test_cli_introspect.py`, `tests/test_cli_classify.py`, `tests/test_cli_discover.py`, `tests/test_cli_command.py`.

---

## Task 1: IR models (`ir.py`)

**Files:**
- Create: `src/phantasos/generator/__init__.py`
- Create: `src/phantasos/generator/cli/__init__.py`
- Create: `src/phantasos/generator/cli/ir.py`
- Test: `tests/test_cli_ir.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_ir.py
from phantasos.generator.cli.ir import CliIR, Command, Flag


def test_flag_defaults():
    f = Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)
    assert f.default is None
    assert f.choices is None
    assert f.help == ""


def test_command_and_ir_roundtrip():
    cmd = Command(
        verb="set", object="widget", sdk_resource="widgets", sdk_method="create_widget",
        body_flags=[Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)],
    )
    ir = CliIR(sdk_package="fakesdk", sdk_version="9.9.9", commands=[cmd])
    assert ir.commands[0].verb == "set"
    assert ir.commands[0].variant is None
    # round-trips through JSON (used for _generated/ir.json in Phase 2)
    assert CliIR.model_validate_json(ir.model_dump_json()) == ir
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_ir.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/phantasos/generator/__init__.py
"""phantasos code generators."""
```

```python
# src/phantasos/generator/cli/__init__.py
"""CLI generator: introspect a built SDK and emit a Typer CLI."""
```

```python
# src/phantasos/generator/cli/ir.py
"""The CLI intermediate representation: the fully-resolved command tree.

Rendered by templates, reported by discovery, and serialized to _generated/ir.json.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

FlagKind = Literal["scalar", "enum", "json", "file", "id"]
Verb = Literal["set", "del", "show", "request", "load", "backup"]


class Flag(BaseModel):
    name: str  # CLI flag, e.g. "--name"
    param: str  # SDK parameter name, e.g. "name"
    py_type: str  # rendered annotation, e.g. "str"
    kind: FlagKind
    required: bool
    default: Any | None = None
    help: str = ""
    choices: list[str] | None = None  # enum values; flag stays permissive (str + completer)


class Command(BaseModel):
    verb: Verb
    object: str  # kebab-case noun, e.g. "application"
    variant: str | None = None  # union variant subcommand, if any
    sdk_resource: str  # facade attribute, e.g. "applications"
    sdk_method: str  # e.g. "create_application"
    path_params: list[Flag] = []
    body_flags: list[Flag] = []
    query_flags: list[Flag] = []
    summary: str = ""
    description: str = ""
    paginated: bool = False


class CliIR(BaseModel):
    sdk_package: str
    sdk_version: str
    commands: list[Command] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_ir.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator tests/test_cli_ir.py
git commit -m "feat(cli-gen): add CliIR data model"
```

---

## Task 2: `cli.yml` config model + loader (`cliconfig.py`)

**Files:**
- Create: `src/phantasos/generator/cli/cliconfig.py`
- Test: `tests/test_cli_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_config.py
from pathlib import Path

from phantasos.generator.cli.cliconfig import CliConfig, load_cli_config


def test_empty_config_when_file_missing(tmp_path):
    cfg = load_cli_config(tmp_path / "nope.yml")
    assert cfg == CliConfig()
    assert cfg.hide == []
    assert cfg.request == {}
    assert cfg.variants == {}


def test_loads_all_sections(tmp_path):
    p = tmp_path / "cli.yml"
    p.write_text(
        "request:\n"
        "  devices.force_reauth_devices: {object: devices, action: force-reauth}\n"
        "override:\n"
        "  applications.create_application: {object: application}\n"
        "hide:\n"
        "  - applications.list_application_categories\n"
        "variants:\n"
        "  applications.create_application:\n"
        "    path_param: type\n"
        "    map: {custom: CustomApplicationInput, private: PrivateApplicationInput}\n"
        "custom:\n"
        "  commands: [pkg.custom.doctor]\n"
    )
    cfg = load_cli_config(p)
    assert cfg.request["devices.force_reauth_devices"].action == "force-reauth"
    assert cfg.override["applications.create_application"].object == "application"
    assert "applications.list_application_categories" in cfg.hide
    v = cfg.variants["applications.create_application"]
    assert v.path_param == "type"
    assert v.map["custom"] == "CustomApplicationInput"
    assert cfg.custom.commands == ["pkg.custom.doctor"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.cliconfig'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/phantasos/generator/cli/cliconfig.py
"""The per-product cli.yml model — declarative deltas only; the classifier always runs.

cli.yml holds: request (non-CRUD remaps), override (fix object/verb), hide (exclude),
variants (REQUIRED path-enum -> variant-model map for union bodies), settings (per-flag
tweaks), custom (pointer to hand-owned commands).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from ruamel.yaml import YAML


class RequestMapping(BaseModel):
    object: str
    action: str


class Override(BaseModel):
    object: str | None = None
    verb: str | None = None
    variant: str | None = None


class VariantMap(BaseModel):
    path_param: str
    map: dict[str, str]  # path-enum value -> variant model class name


class CustomPointer(BaseModel):
    commands: list[str] = []


class CliConfig(BaseModel):
    request: dict[str, RequestMapping] = {}
    override: dict[str, Override] = {}
    hide: list[str] = []
    variants: dict[str, VariantMap] = {}
    settings: dict[str, Any] = {}
    custom: CustomPointer = CustomPointer()


def load_cli_config(path: Path) -> CliConfig:
    """Load cli.yml; return an empty CliConfig if the file is absent."""
    if not path.exists():
        return CliConfig()
    data: dict[str, Any] = YAML(typ="safe").load(path.open(encoding="utf-8")) or {}
    return CliConfig.model_validate(data)
```

Note: `ruamel.yaml` is already used by `productconfig.py` (`_read_yaml`). Reuse it for consistency.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/cliconfig.py tests/test_cli_config.py
git commit -m "feat(cli-gen): add cli.yml config model + loader"
```

---

## Task 3: Test fixture — a fake built SDK

A small in-tree package that mimics a phantasos-built SDK's shape so introspection/classification can be tested deterministically without the real sibling SDK. It exercises every shape the generator must handle: verb-prefixed methods, `_by_id`/`_by_type_and_id`, a varied id name, an enum path param, a union body (undiscriminated, empty map), a `*_positions` reorder op, and excluded `*_serialize`/`*_with_http_info` methods.

**Files:**
- Create: `tests/fixtures/fakesdk/fakesdk/__init__.py`
- Create: `tests/fixtures/fakesdk/fakesdk/models.py`
- Create: `tests/fixtures/fakesdk/fakesdk/api.py`
- Create: `tests/fixtures/fakesdk/fakesdk/extras/__init__.py`
- Create: `tests/fixtures/fakesdk/fakesdk/extras/facade.py`

- [ ] **Step 1: Create the fixture package**

```python
# tests/fixtures/fakesdk/fakesdk/__init__.py
__version__ = "9.9.9"
```

```python
# tests/fixtures/fakesdk/fakesdk/models.py
from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class WidgetType(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


class WidgetInput(BaseModel):
    name: str
    color: Optional[Color] = None
    tags: list[str] = []
    spec: Optional[dict] = None  # nested -> json flag


class SimpleGizmoInput(BaseModel):
    name: str


class ComplexGizmoInput(BaseModel):
    name: str
    depth: int


class CreateGizmoInput(BaseModel):
    """Undiscriminated oneOf wrapper, mirroring OAG output."""

    discriminator_value_class_map: dict = {}  # empty, like the real SDK
    actual_instance: Optional[Union[SimpleGizmoInput, ComplexGizmoInput]] = None
```

```python
# tests/fixtures/fakesdk/fakesdk/api.py
from __future__ import annotations

from .models import CreateGizmoInput, WidgetInput, WidgetType


class WidgetsApi:
    def __init__(self, api_client=None):
        pass

    def create_widget(self, widget_input: WidgetInput):
        """Create a widget.

        Adds a new widget to the system.
        """

    def get_widget_by_id(self, id: str, configuration_version: str | None = None):
        """Get a widget by id."""

    def list_widgets(self, name: str | None = None, limit: int | None = None):
        """List widgets."""

    def delete_widget_by_id(self, id: str):
        """Delete a widget."""

    def patch_widget(self, id: str, widget_input: WidgetInput):
        """Patch a widget."""

    def update_widget_positions(self, body: dict):
        """Reorder widgets."""

    # excluded by introspection:
    def create_widget_with_http_info(self, widget_input: WidgetInput):
        ...

    def _create_widget_serialize(self, widget_input):
        ...


class GizmosApi:
    def __init__(self, api_client=None):
        pass

    def create_gizmo(self, type: WidgetType, create_gizmo_input: CreateGizmoInput):
        """Create a gizmo."""

    def get_gizmo_by_type_and_id(self, type: WidgetType, id: str):
        """Get a gizmo."""

    def list_gizmos(self):
        """List gizmos."""

    def delete_gizmo_by_id(self, id: str):
        """Delete a gizmo."""


class ThingsApi:
    def __init__(self, api_client=None):
        pass

    def get_thing(self, thing_id: str):
        """Get a thing (id param is not literally 'id')."""

    def delete_thing(self, thing_id: str):
        """Delete a thing."""
```

```python
# tests/fixtures/fakesdk/fakesdk/extras/__init__.py
```

```python
# tests/fixtures/fakesdk/fakesdk/extras/facade.py
from ..api import GizmosApi, ThingsApi, WidgetsApi

_RESOURCES = {
    "widgets": WidgetsApi,
    "gizmos": GizmosApi,
    "things": ThingsApi,
}
```

- [ ] **Step 2: Verify the fixture imports**

Run: `uv run python -c "import sys; sys.path.insert(0, 'tests/fixtures/fakesdk'); import fakesdk; from fakesdk.extras.facade import _RESOURCES; print(sorted(_RESOURCES))"`
Expected: `['gizmos', 'things', 'widgets']`

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/fakesdk
git commit -m "test(cli-gen): add fake SDK fixture for introspection tests"
```

---

## Task 4: Introspection (`inventory.py` + `introspect.py`)

**Files:**
- Create: `src/phantasos/generator/cli/inventory.py`
- Create: `src/phantasos/generator/cli/introspect.py`
- Test: `tests/test_cli_introspect.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_introspect.py
from pathlib import Path

import pytest

from phantasos.generator.cli.introspect import introspect

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


@pytest.fixture
def inv():
    return introspect("fakesdk", FIXTURE)


def _op(inv, resource, method):
    return next(o for o in inv.operations if o.resource == resource and o.method == method)


def test_version_and_resources(inv):
    assert inv.sdk_package == "fakesdk"
    assert inv.sdk_version == "9.9.9"
    assert {o.resource for o in inv.operations} == {"widgets", "gizmos", "things"}


def test_excludes_http_info_and_serialize(inv):
    methods = {o.method for o in inv.operations if o.resource == "widgets"}
    assert "create_widget" in methods
    assert "create_widget_with_http_info" not in methods
    assert "_create_widget_serialize" not in methods


def test_path_and_body_params(inv):
    op = _op(inv, "widgets", "create_widget")
    body = [p for p in op.params if p.location == "body"]
    assert body and body[0].name == "widget_input"
    assert body[0].body_model == "WidgetInput"
    assert op.summary == "Create a widget."


def test_enum_param_values(inv):
    op = _op(inv, "gizmos", "create_gizmo")
    type_param = next(p for p in op.params if p.name == "type")
    assert type_param.location == "path"
    assert type_param.enum_values == ["simple", "complex"]


def test_union_body_members(inv):
    op = _op(inv, "gizmos", "create_gizmo")
    body = next(p for p in op.params if p.location == "body")
    assert body.union_members == ["SimpleGizmoInput", "ComplexGizmoInput"]


def test_body_fields_recursed(inv):
    op = _op(inv, "widgets", "create_widget")
    fields = op.body_fields["WidgetInput"]
    by_name = {f.name: f for f in fields}
    assert by_name["name"].kind == "scalar" and by_name["name"].required
    assert by_name["color"].kind == "enum" and by_name["color"].enum_values == ["red", "blue"]
    assert by_name["spec"].kind == "json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_introspect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.introspect'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/phantasos/generator/cli/inventory.py
"""Typed output of SDK introspection (the input to classification)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from .ir import FlagKind

Location = Literal["path", "query", "body"]


class ParamInfo(BaseModel):
    name: str
    annotation: str
    location: Location
    required: bool
    default: Any | None = None
    description: str = ""
    enum_values: list[str] | None = None
    body_model: str | None = None  # set when location == "body"
    union_members: list[str] | None = None  # variant model names if the body is a oneOf wrapper


class FieldInfo(BaseModel):
    name: str
    annotation: str
    kind: FlagKind
    required: bool
    default: Any | None = None
    description: str = ""
    enum_values: list[str] | None = None


class OperationInfo(BaseModel):
    resource: str
    method: str
    summary: str = ""
    description: str = ""
    params: list[ParamInfo] = []
    body_fields: dict[str, list[FieldInfo]] = {}  # model/variant name -> fields
    return_type: str = ""


class OperationInventory(BaseModel):
    sdk_package: str
    sdk_version: str
    operations: list[OperationInfo] = []
```

```python
# src/phantasos/generator/cli/introspect.py
"""Import a built SDK and produce a typed OperationInventory."""

from __future__ import annotations

import enum
import importlib
import inspect
import sys
import typing
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from .inventory import FieldInfo, OperationInfo, OperationInventory, ParamInfo

_EXCLUDE_SUFFIXES = ("_with_http_info", "_without_preload_content", "_serialize")
_SKIP_PARAMS = {"self", "_request_timeout", "_request_auth", "_content_type", "_headers", "_host_index"}


def _public_methods(cls: type):
    for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith("_") or name.endswith(_EXCLUDE_SUFFIXES):
            continue
        yield name, member


def _enum_values(tp) -> list[str] | None:
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return [str(m.value) for m in tp]
    return None


def _unwrap_optional(tp):
    """Return the non-None member of Optional[X], else tp."""
    if get_origin(tp) in (Union, UnionType):
        non_none = [a for a in get_args(tp) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return tp


def _field_kind(tp) -> str:
    tp = _unwrap_optional(tp)
    if _enum_values(tp):
        return "enum"
    if tp in (str, int, float, bool):
        return "scalar"
    origin = get_origin(tp)
    if origin in (list, set):
        inner = _unwrap_optional(get_args(tp)[0]) if get_args(tp) else str
        return "scalar" if inner in (str, int, float, bool) else "json"
    return "json"  # nested model, dict, union, etc.


def _model_fields(model: type[BaseModel]) -> list[FieldInfo]:
    out: list[FieldInfo] = []
    for fname, field in model.model_fields.items():
        tp = field.annotation
        out.append(
            FieldInfo(
                name=fname,
                annotation=str(tp),
                kind=_field_kind(tp),
                required=field.is_required(),
                default=None if field.is_required() else field.default,
                description=field.description or "",
                enum_values=_enum_values(_unwrap_optional(tp)),
            )
        )
    return out


def _union_members(model: type[BaseModel]) -> list[str] | None:
    field = model.model_fields.get("actual_instance")
    if field is None:
        return None
    inner = _unwrap_optional(field.annotation)
    if get_origin(inner) in (Union, UnionType):
        return [a.__name__ for a in get_args(inner) if a is not type(None)]
    return None


def _docstring_parts(fn) -> tuple[str, str]:
    doc = inspect.getdoc(fn) or ""
    if not doc:
        return "", ""
    head, _, rest = doc.partition("\n\n")
    return head.strip(), rest.strip()


def introspect(package: str, sdk_path: Path) -> OperationInventory:
    if str(sdk_path) not in sys.path:
        sys.path.insert(0, str(sdk_path))
    pkg = importlib.import_module(package)
    facade = importlib.import_module(f"{package}.extras.facade")
    resources: dict[str, type] = facade._RESOURCES

    operations: list[OperationInfo] = []
    for resource, api_cls in resources.items():
        hints_cache: dict[str, dict] = {}
        for method, fn in _public_methods(api_cls):
            try:
                hints = typing.get_type_hints(fn, include_extras=False)
            except Exception:
                hints = {}
            hints_cache[method] = hints
            sig = inspect.signature(fn)
            summary, description = _docstring_parts(fn)
            params: list[ParamInfo] = []
            body_fields: dict[str, list[FieldInfo]] = {}
            for pname, p in sig.parameters.items():
                if pname in _SKIP_PARAMS:
                    continue
                tp = hints.get(pname, p.annotation)
                base = _unwrap_optional(tp)
                required = p.default is inspect.Parameter.empty
                is_body = isinstance(base, type) and issubclass(base, BaseModel)
                location = "body" if is_body else ("query" if not required else "path")
                # required scalars with no default are path params; optional are query
                if not is_body and not required:
                    location = "query"
                info = ParamInfo(
                    name=pname,
                    annotation=str(tp),
                    location=location,
                    required=required,
                    default=None if required else p.default,
                    enum_values=_enum_values(base),
                )
                if is_body:
                    info.body_model = base.__name__
                    members = _union_members(base)
                    info.union_members = members
                    if members:
                        ns = sys.modules[base.__module__]
                        for m in members:
                            body_fields[m] = _model_fields(getattr(ns, m))
                    else:
                        body_fields[base.__name__] = _model_fields(base)
                params.append(info)
            operations.append(
                OperationInfo(
                    resource=resource, method=method, summary=summary,
                    description=description, params=params, body_fields=body_fields,
                )
            )
    return OperationInventory(
        sdk_package=package,
        sdk_version=getattr(pkg, "__version__", "0.0.0"),
        operations=operations,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_introspect.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/inventory.py src/phantasos/generator/cli/introspect.py tests/test_cli_introspect.py
git commit -m "feat(cli-gen): introspect a built SDK into a typed OperationInventory"
```

---

## Task 5: Classification — verb/noun + precedence (`classify.py`)

**Files:**
- Create: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test** (corpus seeded from the real prisma-browser inventory)

```python
# tests/test_cli_classify.py
import pytest

from phantasos.generator.cli.classify import classify_name


@pytest.mark.parametrize(
    "method,verb,obj",
    [
        ("create_application", "set", "application"),
        ("patch_application_by_type_and_id", "set", "application"),
        ("update_device_group", "set", "device-group"),
        ("delete_application_by_id", "del", "application"),
        ("bulk_delete_applications", "del", "application"),
        ("get_application_by_id", "show", "application"),
        ("list_applications", "show", "application"),
        ("list_device_groups", "show", "device-group"),
        ("bulk_create_applications", "set", "application"),
        ("create_access_and_data_rule", "set", "access-and-data-rule"),
    ],
)
def test_classify_verb_and_noun(method, verb, obj):
    c = classify_name(method)
    assert c is not None
    assert (c.verb, c.object) == (verb, obj)


@pytest.mark.parametrize(
    "method",
    [
        "update_access_and_data_positions",  # reorder, not a "position" object
        "force_reauth_devices",
        "suspend_users",
        "revoke_user_request",
        "publish_draft_configuration",
        "action_user_request",
    ],
)
def test_unmapped_returns_none(method):
    assert classify_name(method) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.classify'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/phantasos/generator/cli/classify.py
"""Deterministic classification of SDK methods into the CLI command tree.

Precedence (applied in build_cli_ir): cli.yml hide/skip > cli.yml override/request >
prefix heuristic. classify_name implements only the prefix heuristic + skip rules.
"""

from __future__ import annotations

from pydantic import BaseModel

from .ir import Verb

# (prefix, verb) — ORDER MATTERS: longer/compound prefixes first.
_VERB_PREFIXES: list[tuple[str, Verb]] = [
    ("bulk_create_", "set"),
    ("bulk_delete_", "del"),
    ("create_", "set"),
    ("update_", "set"),
    ("patch_", "set"),
    ("delete_", "del"),
    ("get_", "show"),
    ("list_", "show"),
]

# Method-name fragments that mark non-CRUD ops to skip even if a verb prefix matches.
_SKIP_FRAGMENTS = ("_positions",)


class Classification(BaseModel):
    verb: Verb
    object: str  # kebab-case noun


def _strip_id_suffix(noun: str) -> str:
    for suffix in ("_by_type_and_id", "_by_id", "_by_type"):
        if noun.endswith(suffix):
            return noun[: -len(suffix)]
    return noun


def _singularize(noun: str) -> str:
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    if noun.endswith("ses"):
        return noun[:-2]
    if noun.endswith("s") and not noun.endswith("ss"):
        return noun[:-1]
    return noun


def classify_name(method: str) -> Classification | None:
    """Prefix-heuristic classification. Returns None for unmapped/skip ops."""
    if any(frag in method for frag in _SKIP_FRAGMENTS):
        return None
    for prefix, verb in _VERB_PREFIXES:
        if method.startswith(prefix):
            noun = _strip_id_suffix(method[len(prefix):])
            noun = _singularize(noun)
            return Classification(verb=verb, object=noun.replace("_", "-"))
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS (16 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): classify method names to verb + object noun"
```

---

## Task 6: ID detection + multi-method selection

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_cli_classify.py  (append)
from phantasos.generator.cli.classify import detect_id_param
from phantasos.generator.cli.inventory import ParamInfo


def _p(name, location, required=True, enum_values=None):
    return ParamInfo(name=name, annotation="str", location=location,
                     required=required, enum_values=enum_values)


def test_detect_id_literal():
    params = [_p("id", "path")]
    assert detect_id_param(params).name == "id"


def test_detect_id_nonliteral_name():
    params = [_p("thing_id", "path")]
    assert detect_id_param(params).name == "thing_id"


def test_detect_id_ignores_discriminator_enum():
    # type is a path enum (discriminator), id is the real id
    params = [_p("type", "path", enum_values=["simple", "complex"]), _p("id", "path")]
    assert detect_id_param(params).name == "id"


def test_detect_id_none_when_no_path_id():
    params = [_p("name", "query", required=False)]
    assert detect_id_param(params) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: FAIL with `ImportError: cannot import name 'detect_id_param'`

- [ ] **Step 3: Write minimal implementation (append to `classify.py`)**

```python
# src/phantasos/generator/cli/classify.py  (append)
from .inventory import ParamInfo


def detect_id_param(params: list[ParamInfo]) -> ParamInfo | None:
    """The id is the single required path param that is not a discriminator enum.

    Works before the SDK id-name harmonization lands (handles id, device_group_id, etc.).
    """
    candidates = [p for p in params if p.location == "path" and not p.enum_values]
    if not candidates:
        return None
    # Prefer an exactly-named "id"; else the first non-enum path param.
    for p in candidates:
        if p.name == "id":
            return p
    return candidates[0]


def select_method_for_verb(methods: list[str]) -> str:
    """When an object has multiple methods of the same verb (e.g. two delete_* variants),
    prefer the shortest method name (fewest path params); ties broken alphabetically."""
    return sorted(methods, key=lambda m: (m.count("_"), m))[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS (20 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): detect id param + multi-method selection"
```

---

## Task 7: Flag generation from model fields (permissive enums)

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_cli_classify.py  (append)
from phantasos.generator.cli.classify import fields_to_flags
from phantasos.generator.cli.inventory import FieldInfo


def test_fields_to_flags_kinds():
    fields = [
        FieldInfo(name="name", annotation="str", kind="scalar", required=True),
        FieldInfo(name="color", annotation="Color", kind="enum", required=False,
                  enum_values=["red", "blue"]),
        FieldInfo(name="spec", annotation="dict", kind="json", required=False),
    ]
    flags = {f.param: f for f in fields_to_flags(fields)}
    assert flags["name"].name == "--name" and flags["name"].required
    # enum stays permissive: kind == enum, choices populated, but py_type is str
    assert flags["color"].kind == "enum"
    assert flags["color"].choices == ["red", "blue"]
    assert flags["color"].py_type == "str"
    assert flags["spec"].kind == "json"


def test_snake_case_field_becomes_kebab_flag():
    fields = [FieldInfo(name="ip_netmask", annotation="str", kind="scalar", required=True)]
    assert fields_to_flags(fields)[0].name == "--ip-netmask"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: FAIL with `ImportError: cannot import name 'fields_to_flags'`

- [ ] **Step 3: Write minimal implementation (append to `classify.py`)**

```python
# src/phantasos/generator/cli/classify.py  (append)
from .inventory import FieldInfo
from .ir import Flag


def _flag_name(param: str) -> str:
    return "--" + param.replace("_", "-")


def fields_to_flags(fields: list[FieldInfo]) -> list[Flag]:
    flags: list[Flag] = []
    for f in fields:
        # Enum flags stay permissive: emit str + completer choices, never a validating Enum
        # (the SDK uses LenientStrEnum — unknown values must pass through).
        py_type = "str" if f.kind == "enum" else f.annotation
        flags.append(
            Flag(
                name=_flag_name(f.name),
                param=f.name,
                py_type=py_type,
                kind=f.kind,
                required=f.required,
                default=f.default,
                help=f.description,
                choices=f.enum_values,
            )
        )
    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS (22 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): generate permissive flags from model fields"
```

---

## Task 8: Variant resolution from `cli.yml`

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_cli_classify.py  (append)
from phantasos.generator.cli.classify import resolve_variants
from phantasos.generator.cli.cliconfig import VariantMap
from phantasos.generator.cli.inventory import OperationInfo, ParamInfo


def test_resolve_variants_from_config():
    op = OperationInfo(
        resource="gizmos", method="create_gizmo",
        params=[
            ParamInfo(name="type", annotation="WidgetType", location="path",
                      required=True, enum_values=["simple", "complex"]),
            ParamInfo(name="create_gizmo_input", annotation="CreateGizmoInput",
                      location="body", required=True, body_model="CreateGizmoInput",
                      union_members=["SimpleGizmoInput", "ComplexGizmoInput"]),
        ],
        body_fields={
            "SimpleGizmoInput": [FieldInfo(name="name", annotation="str", kind="scalar", required=True)],
            "ComplexGizmoInput": [FieldInfo(name="name", annotation="str", kind="scalar", required=True),
                                  FieldInfo(name="depth", annotation="int", kind="scalar", required=True)],
        },
    )
    vmap = VariantMap(path_param="type", map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"})
    variants = resolve_variants(op, vmap)
    assert [v.name for v in variants] == ["simple", "complex"]
    assert variants[1].model == "ComplexGizmoInput"


def test_resolve_variants_none_without_config():
    op = OperationInfo(resource="widgets", method="create_widget")
    assert resolve_variants(op, None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_variants'`

- [ ] **Step 3: Write minimal implementation (append to `classify.py`)**

```python
# src/phantasos/generator/cli/classify.py  (append)
from .cliconfig import VariantMap
from .inventory import OperationInfo


class ResolvedVariant(BaseModel):
    name: str  # path-enum value, e.g. "custom"
    model: str  # variant model class name, e.g. "CustomApplicationInput"


def resolve_variants(op: OperationInfo, vmap: VariantMap | None) -> list[ResolvedVariant]:
    """Map a method's path-enum values to variant models via cli.yml (the SDK oneOf
    wrapper is undiscriminated, so this mapping must be authored)."""
    if vmap is None:
        return []
    return [ResolvedVariant(name=value, model=model) for value, model in vmap.map.items()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS (24 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): resolve union variants from cli.yml"
```

---

## Task 9: Assemble the full `CliIR` (`build_cli_ir`)

Composes the helpers, applying precedence: `hide` → `override`/`request` → prefix heuristic. Returns the `CliIR` plus the list of unmapped `resource.method` keys (for discovery warnings).

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_cli_classify.py  (append)
from pathlib import Path

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig, VariantMap
from phantasos.generator.cli.introspect import introspect

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_build_cli_ir_end_to_end():
    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(
        variants={
            "gizmos.create_gizmo": VariantMap(
                path_param="type",
                map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
            )
        }
    )
    ir, unmapped = build_cli_ir(inv, cfg)
    cmds = {(c.verb, c.object, c.variant): c for c in ir.commands}

    # CRUD on widgets
    assert ("set", "widget", None) in cmds
    assert ("show", "widget", None) in cmds
    assert ("del", "widget", None) in cmds

    # set widget has body flags incl. the detected id flag absent on create
    setw = cmds[("set", "widget", None)]
    assert any(f.name == "--name" for f in setw.body_flags)

    # gizmo create fans out into variant subcommands
    assert ("set", "gizmo", "simple") in cmds
    assert ("set", "gizmo", "complex") in cmds
    complex_cmd = cmds[("set", "gizmo", "complex")]
    assert any(f.name == "--depth" for f in complex_cmd.body_flags)

    # things use a non-literal id param
    show_thing = cmds[("show", "thing", None)]
    assert any(f.kind == "id" and f.param == "thing_id" for f in show_thing.path_params)

    # *_positions is unmapped
    assert "widgets.update_widget_positions" in unmapped

    assert ir.sdk_version == "9.9.9"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py::test_build_cli_ir_end_to_end -v`
Expected: FAIL with `ImportError: cannot import name 'build_cli_ir'`

- [ ] **Step 3: Write minimal implementation (append to `classify.py`)**

```python
# src/phantasos/generator/cli/classify.py  (append)
from .cliconfig import CliConfig
from .inventory import OperationInventory
from .ir import CliIR, Command


def _id_flag(param: ParamInfo) -> Flag:
    return Flag(name="--id", param=param.name, py_type="str", kind="id",
                required=True, help=param.description)


def _query_flags(params: list[ParamInfo]) -> list[Flag]:
    return [
        Flag(name=_flag_name(p.name), param=p.name,
             py_type="str" if p.enum_values else "str", kind="enum" if p.enum_values else "scalar",
             required=False, default=p.default, help=p.description, choices=p.enum_values)
        for p in params if p.location == "query"
    ]


def _body_flags_for(op: OperationInfo, model: str | None) -> list[Flag]:
    if model and model in op.body_fields:
        return fields_to_flags(op.body_fields[model])
    # single (non-union) body model
    for fields in op.body_fields.values():
        return fields_to_flags(fields)
    return []


def build_cli_ir(inv: OperationInventory, cfg: CliConfig) -> tuple[CliIR, list[str]]:
    commands: list[Command] = []
    unmapped: list[str] = []
    for op in inv.operations:
        key = f"{op.resource}.{op.method}"
        if key in cfg.hide:
            continue
        ov = cfg.override.get(key)
        cls = classify_name(op.method)
        if cls is None and key not in cfg.request:
            unmapped.append(key)
            continue
        if key in cfg.request:
            # request-namespace ops are handled in a later phase; skip here but don't warn
            continue
        verb = ov.verb if ov and ov.verb else cls.verb
        obj = ov.object if ov and ov.object else cls.object
        id_param = detect_id_param(op.params)
        path_flags = [_id_flag(id_param)] if id_param else []
        query_flags = _query_flags(op.params)
        variants = resolve_variants(op, cfg.variants.get(key))
        if variants:
            for v in variants:
                commands.append(Command(
                    verb=verb, object=obj, variant=v.name,
                    sdk_resource=op.resource, sdk_method=op.method,
                    path_params=path_flags, body_flags=_body_flags_for(op, v.model),
                    query_flags=query_flags, summary=op.summary, description=op.description,
                    paginated=op.method.startswith("list_"),
                ))
        else:
            commands.append(Command(
                verb=verb, object=obj, variant=None,
                sdk_resource=op.resource, sdk_method=op.method,
                path_params=path_flags, body_flags=_body_flags_for(op, None),
                query_flags=query_flags, summary=op.summary, description=op.description,
                paginated=op.method.startswith("list_"),
            ))
    ir = CliIR(sdk_package=inv.sdk_package, sdk_version=inv.sdk_version, commands=commands)
    return ir, unmapped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS (25 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): assemble full CliIR with precedence + variants"
```

---

## Task 10: Discover — table + `cli.yml` stub (`discover.py`)

**Files:**
- Create: `src/phantasos/generator/cli/discover.py`
- Test: `tests/test_cli_discover.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_discover.py
from pathlib import Path

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.discover import render_stub, render_table
from phantasos.generator.cli.introspect import introspect

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def _ir_and_unmapped():
    inv = introspect("fakesdk", FIXTURE)
    return build_cli_ir(inv, CliConfig())


def test_render_table_lists_commands_and_unmapped():
    ir, unmapped = _ir_and_unmapped()
    table = render_table(ir, unmapped)
    assert "set widget" in table
    assert "show widget" in table
    assert "UNMAPPED" in table
    assert "widgets.update_widget_positions" in table


def test_render_stub_is_valid_yaml_with_todos():
    import io

    from ruamel.yaml import YAML

    ir, unmapped = _ir_and_unmapped()
    stub = render_stub(ir, unmapped)
    data = YAML(typ="safe").load(io.StringIO(stub))
    # unmapped ops appear under a commented TODO section as request/hide candidates
    assert "request" in data or "hide" in data
    assert "update_widget_positions" in stub  # surfaced as a TODO
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_discover.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'phantasos.generator.cli.discover'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/phantasos/generator/cli/discover.py
"""Render the classification table and a cli.yml stub from a CliIR."""

from __future__ import annotations

from .ir import CliIR


def render_table(ir: CliIR, unmapped: list[str]) -> str:
    lines = [f"# {ir.sdk_package} {ir.sdk_version} — {len(ir.commands)} commands"]
    for c in sorted(ir.commands, key=lambda c: (c.verb, c.object, c.variant or "")):
        target = f"{c.verb} {c.object}" + (f" {c.variant}" if c.variant else "")
        lines.append(f"  {target:<40} <- {c.sdk_resource}.{c.sdk_method}")
    if unmapped:
        lines.append(f"\n# UNMAPPED ({len(unmapped)}) — map in cli.yml (request:/override:/hide:)")
        for key in sorted(unmapped):
            lines.append(f"  UNMAPPED  {key}")
    return "\n".join(lines)


def render_stub(ir: CliIR, unmapped: list[str]) -> str:
    """A cli.yml stub: TODO entries for unmapped ops. CRUD is auto-classified, so the
    stub only needs the deltas the author must fill in."""
    lines = [
        "# cli.yml stub — generated by `phantasos cli discover`.",
        "# CRUD ops are auto-classified; fill in the non-CRUD ops below.",
        "request:",
    ]
    for key in sorted(unmapped):
        obj = key.split(".")[0].rstrip("s")
        lines.append(f"  # TODO: map {key}")
        lines.append(f"  # {key}: {{object: {obj}, action: CHANGE_ME}}")
    lines.append("hide: []")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_discover.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/discover.py tests/test_cli_discover.py
git commit -m "feat(cli-gen): render discover table + cli.yml stub"
```

---

## Task 11: Wire `phantasos cli discover` into the CLI

**Files:**
- Modify: `src/phantasos/cli.py`
- Test: `tests/test_cli_command.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_command.py
from pathlib import Path

from phantasos.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_cli_discover_prints_table(capsys, monkeypatch):
    # Stub load_product so the command resolves package + sdk path to the fixture.
    import phantasos.cli as climod

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
        base_dir = FIXTURE
        output_dir = FIXTURE

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    rc = main(["cli", "discover", "fakesdk"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "set widget" in out
    assert "UNMAPPED" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_command.py -v`
Expected: FAIL — `cli` subcommand does not exist (argparse error / nonzero rc).

- [ ] **Step 3: Write minimal implementation** (modify `src/phantasos/cli.py`)

Add a `cli` subparser group with a `discover` sub-subcommand. Insert after the existing `build` parser block (after line 23) and add the dispatch branch before `return 0` (line 56):

```python
# in main(), after the existing `b.add_argument(... --no-smoke ...)` block:
    cli_p = sub.add_parser("cli", help="generate / inspect a CLI from a built SDK")
    cli_sub = cli_p.add_subparsers(dest="cli_cmd", required=True)
    disc = cli_sub.add_parser("discover", help="print the classification table + cli.yml stub")
    disc.add_argument("product", help="product name (products/<name>/) or path to sdk.yml")
    disc.add_argument("--write-stub", action="store_true",
                      help="write products/<name>/cli.yml.stub next to sdk.yml")
```

```python
# in main(), add this branch (before the final `return 0`):
    if args.cmd == "cli" and args.cli_cmd == "discover":
        from pathlib import Path

        from .generator.cli.classify import build_cli_ir
        from .generator.cli.cliconfig import load_cli_config
        from .generator.cli.discover import render_stub, render_table
        from .generator.cli.introspect import introspect

        try:
            loaded = load_product(args.product)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
        try:
            inv = introspect(loaded.config.package, Path(loaded.output_dir))
        except ImportError as exc:
            print(f"ERROR: SDK not importable — build it first ({exc})", file=sys.stderr)
            return 2
        ir, unmapped = build_cli_ir(inv, cfg)
        print(render_table(ir, unmapped))
        if getattr(args, "write_stub", False):
            stub_path = Path(loaded.base_dir) / "cli.yml.stub"
            stub_path.write_text(render_stub(ir, unmapped), encoding="utf-8")
            print(f"\nwrote {stub_path}", file=sys.stderr)
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_command.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the full suite + lint/type checks**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos/generator && uv run mypy src/phantasos/generator`
Expected: all pass (mypy strict per repo config).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/cli.py tests/test_cli_command.py
git commit -m "feat(cli-gen): wire 'phantasos cli discover' command"
```

---

## Task 12: Smoke against the real SDK (optional, gated)

A non-fixture sanity check: if the real `../prisma-browser-sdk` is built/importable, discover must classify without crashing and produce the expected verb spread.

**Files:**
- Test: `tests/test_cli_discover.py` (append)

- [ ] **Step 1: Write the gated test**

```python
# tests/test_cli_discover.py  (append)
import importlib.util

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect

REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_real_sdk_classifies_without_error():
    inv = introspect("prisma_browser", REAL_SDK)
    ir, unmapped = build_cli_ir(inv, CliConfig())
    verbs = {c.verb for c in ir.commands}
    assert {"set", "del", "show"} <= verbs
    # non-CRUD ops land in unmapped (force_reauth/positions/etc.)
    assert any("positions" in u or "force" in u or "publish" in u for u in unmapped)
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_cli_discover.py::test_real_sdk_classifies_without_error -v`
Expected: PASS if the SDK is built, else SKIPPED. If it FAILS, the classifier hit a real shape the fixture missed — capture that method in the fixture and fix the rule before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_discover.py
git commit -m "test(cli-gen): gated smoke against the real prisma-browser SDK"
```

---

## Self-review (completed during authoring)

- **Spec coverage:** introspect (§Architecture) → Task 4; classifier rules + precedence + id detection + multi-method (§Classifier) → Tasks 5,6,9; flag gen + permissive enums (§Flag generation) → Task 7; oneOf via cli.yml variants (§Grammar, §cli.yml) → Tasks 2,8,9; cli.yml override-only model (§cli.yml) → Task 2; discover table + stub as required artifact (§Generation commands) → Tasks 10,11; CliIR + SDK provenance (§CliIR) → Tasks 1,4,9. **Deferred to Phase 2/3 (out of this plan):** all emission/rendering, `_generated/`-vs-hand-owned split, runtime/output/config, `phantasos cli build`, the `request`/`load`/`backup` command bodies (Task 9 intentionally skips `request:` ops without warning, leaving them for Phase 3), completion, command-reference docs.
- **Placeholder scan:** none — every code step is complete.
- **Type consistency:** `Flag`/`Command`/`CliIR` (Task 1) reused verbatim in Tasks 7,9; `ParamInfo`/`FieldInfo`/`OperationInfo`/`OperationInventory` (Task 4) reused in Tasks 6,8,9; `Classification`/`classify_name` (Task 5) used in Task 9; `VariantMap` (Task 2) used in Task 8; `detect_id_param`/`fields_to_flags`/`resolve_variants`/`build_cli_ir` signatures match across tasks.

## Known follow-ups for Phase 2

- `request:`-mapped ops are parsed by `CliConfig` but not yet turned into commands (Phase 3).
- `select_method_for_verb` (Task 6) is defined but only exercised when an object has two same-verb methods; Phase 2 wires it where commands collide.
- `settings:` (per-flag tweaks) is parsed but not yet applied to flags.
