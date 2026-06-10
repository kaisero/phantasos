# CLI Generator: Table Columns (curated table output) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** User-friendly `--output table` for the generated CLI: build-time curated columns per object (cli.yml `columns:` with JMESPath, validated against the response models), a model-derived default heuristic, and a runtime `--columns` override flag.

**Architecture:** Introspection captures each operation's *response* model (mirroring the existing body capture): the return annotation, the list-envelope items field (e.g. `data: List[DeviceGroup]`), and the item model's fields. `build_cli_ir` resolves per-command `ColumnSpec`s — cli.yml `columns:` (JMESPath, build-time-validated) or a preferred-field heuristic — into the IR, so ir.json carries them to the emitted runtime. The emitted `output.py` renders tables by evaluating JMESPath per row; `--columns` overrides at runtime and implies table output. `discover` pre-fills a `columns:` stub.

**Tech Stack:** jmespath (same library the AWS CLI uses), existing Typer/Rich/Jinja pipeline.

**Branch / repo:** `cli-generator` at `/home/ubuntu/git/phantasos` (run all commands from there).

**Test invocation (sshfs venv workaround):** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest ...`

---

## Locked design decisions (from brainstorming, 2026-06-10)

1. **Default columns** when no cli.yml mapping: derived at **build time** from the response item model — preferred names (`id`, `name`, `type`, `status`, `state`) first, then remaining scalar/enum top-level fields, cap 6. A data-driven runtime heuristic remains only as last-resort fallback (response model not introspectable).
2. **cli.yml `columns:`** — per-object list of JMESPath expressions (string shorthand) or `{header, path}` entries. Validated at build time: JMESPath syntax always; the root field name against the item model's fields (build FAILS on violation). `discover` pre-fills the stub with the derived defaults.
3. **Runtime `--columns`** — repeatable flag, comma-separated JMESPath expressions, optional `HEADER=expr` headers. Passing it **implies `--output table`**. No `-o wide`.
4. **Arrays render as joined preview** — `a, b, c, +2 more` (first 3); lists of objects label by `name`/`id`, else `N items`. Nested objects in a cell render as compact JSON.
5. **Row keys are snake_case**: the emitted `output._to_data` uses `model_dump(mode="json")` *without* `by_alias`, so JMESPath paths reference Python field names (`page_info`, not `pageInfo`). Build-time validation against `model_fields` names is consistent with this.

## Verified facts the plan relies on (firsthand, 2026-06-10)

- Real SDK list ops return an **envelope model**: `list_device_groups(...) -> ListDeviceGroups200Response` with `page_info: Optional[PageInfo]` + `data: Optional[List[DeviceGroup]]` (verified in `/home/ubuntu/git/prisma-browser-sdk/prisma_browser/`). `get_*` ops return the item model directly. So table rendering of a bare `show <obj>` currently renders the ENVELOPE as one row — rows extraction via an IR-carried `items_field` fixes this.
- `OperationInfo` already has an (unused, never-populated) `return_type: str = ""` field — leave it; add new typed fields.
- The fakesdk fixture's methods have **no return annotations** — Task 1 adds them (with `from __future__ import annotations` in the file, `typing.get_type_hints` resolves them fine).
- `render_cli` copies `ir.py` verbatim to `_generated/spec.py` (H1), so new IR models are available to the emitted runtime for free.
- `_RESERVED` in render_cli.py already contains `output`, `all_`, `dry_run`, `verbose` — Task 6 must add `columns` so a body field named `columns` can't collide with the injected option.
- jmespath `compile()` returns a `ParsedResult` with `.parsed` (AST dict) and `.search(data)`.

## File structure

| File | Change |
|---|---|
| `tests/fixtures/fakesdk/fakesdk/models.py` | Add `Widget`, `WidgetList` (envelope) response models |
| `tests/fixtures/fakesdk/fakesdk/api.py` | Add return annotations to widget CRUD methods |
| `src/phantasos/generator/cli/inventory.py` | `OperationInfo` += `return_model`, `items_field`, `response_fields` |
| `src/phantasos/generator/cli/introspect.py` | Capture return annotation → `_response_info()` |
| `src/phantasos/generator/cli/ir.py` | New `ColumnSpec`; `Command` += `columns`, `items_field` |
| `src/phantasos/generator/cli/cliconfig.py` | `CliConfig` += `columns:` section (`ColumnEntry`) |
| `src/phantasos/generator/cli/columns.py` | **New**: `default_columns()`, `resolve_columns()` (validation) |
| `src/phantasos/generator/cli/classify.py` | `build_cli_ir`: second pass attaches columns + items_field |
| `src/phantasos/generator/cli/templates/_generated/output.py.jinja` | Table renderer: rows extraction, JMESPath cells, previews, `--columns` parsing, heuristic fallback |
| `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` | `run(..., columns=None)`; columns implies table; pass specs to render |
| `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` | Emit `--columns` option |
| `src/phantasos/generator/cli/render_cli.py` | Add `"columns"` to `_RESERVED` |
| `src/phantasos/generator/cli/scaffold_context.py` | `_CLI_DEPS` += `jmespath>=1.0` |
| `src/phantasos/generator/cli/discover.py` | Stub pre-fills `columns:` |
| `pyproject.toml` | phantasos deps += `jmespath>=1.0`; mypy override for untyped `jmespath` |
| `products/prisma-browser/cli.yml` | Author curated `columns:` for key objects |
| `docs/superpowers/specs/2026-06-09-cli-generator-design.md` | Spec sync: table-columns section |

---

### Task 1: fakesdk fixture — response models + return annotations

**Files:**
- Modify: `tests/fixtures/fakesdk/fakesdk/models.py`
- Modify: `tests/fixtures/fakesdk/fakesdk/api.py`

The fixture currently has input models only and methods returning nothing. Add a response item model + a list envelope mirroring the real SDK shape, and annotate returns. This is fixture-only; the test that locks it in lands in Task 2 (introspect capture).

- [ ] **Step 1: Add response models to models.py**

Append to `tests/fixtures/fakesdk/fakesdk/models.py`:

```python
class Widget(BaseModel):
    """Response item model (what get returns; what the list envelope contains)."""

    id: str
    name: str
    color: Optional[Color] = None
    priority: int = 0
    enabled: Optional[bool] = None
    tags: list[str] = []
    spec: Optional[dict] = None          # nested -> excluded from default columns
    members: list[dict] = []             # list-of-objects -> joined preview


class PageInfo(BaseModel):
    cursor: Optional[str] = None


class WidgetList(BaseModel):
    """List envelope, mirroring the real SDK's List*200Response shape."""

    page_info: Optional[PageInfo] = None
    data: Optional[list[Widget]] = None
```

- [ ] **Step 2: Annotate returns in api.py**

In `tests/fixtures/fakesdk/fakesdk/api.py`, extend the import and annotate the widget methods (leave gizmos/things WITHOUT return annotations — they become the "no response model" coverage):

```python
from .models import CreateGizmoInput, Widget, WidgetInput, WidgetList, WidgetType
```

```python
    def create_widget(self, widget_input: WidgetInput) -> Widget:
```
```python
    def get_widget_by_id(
        self,
        id: Annotated[str, Field(description="The widget id.")],
        configuration_version: str | None = None,
    ) -> Widget:
```
```python
    def list_widgets(self, name: str | None = None, limit: int | None = None) -> WidgetList:
```
```python
    def patch_widget(self, id: str, widget_input: WidgetInput) -> Widget:
```
```python
    def update_widget(self, id: str, widget_input: WidgetInput) -> Widget:
```

(`delete_widget_by_id`, the request actions, and all of GizmosApi/ThingsApi stay unannotated.)

- [ ] **Step 3: Run the existing suite to prove no regression**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -x -q`
Expected: all pass (fixture change is additive).

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/fakesdk/
git commit -m "test(cli-gen): fakesdk response models + return annotations (columns groundwork)"
```

---

### Task 2: introspect — capture response model, items field, item fields

**Files:**
- Modify: `src/phantasos/generator/cli/inventory.py`
- Modify: `src/phantasos/generator/cli/introspect.py`
- Test: `tests/test_cli_introspect.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_introspect.py` (follow the file's existing helper for getting an op; if it has one like `_op(inv, resource, method)`, reuse it — otherwise this standalone form works):

```python
def test_response_capture_list_envelope(inventory):
    op = next(o for o in inventory.operations
              if o.resource == "widgets" and o.method == "list_widgets")
    assert op.return_model == "WidgetList"
    assert op.items_field == "data"
    names = [f.name for f in op.response_fields]
    assert "id" in names and "name" in names  # item (Widget) fields, not envelope's


def test_response_capture_get_returns_item_directly(inventory):
    op = next(o for o in inventory.operations
              if o.resource == "widgets" and o.method == "get_widget_by_id")
    assert op.return_model == "Widget"
    assert op.items_field is None
    kinds = {f.name: f.kind for f in op.response_fields}
    assert kinds["spec"] == "json"      # nested dict
    assert kinds["tags"] == "scalar"    # list[str] counts as scalar kind


def test_response_capture_absent_when_unannotated(inventory):
    op = next(o for o in inventory.operations
              if o.resource == "gizmos" and o.method == "list_gizmos")
    assert op.return_model is None
    assert op.items_field is None
    assert op.response_fields == []
```

Note: `inventory` here is whatever fixture the file already uses to introspect the fakesdk (it exists — the file already tests `introspect("fakesdk", FIXTURE)`); match its name.

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_introspect.py -q`
Expected: FAIL — `OperationInfo` has no `return_model` (ValidationError or AttributeError).

- [ ] **Step 3: Extend OperationInfo**

In `src/phantasos/generator/cli/inventory.py`, add to `OperationInfo` (below `return_type`):

```python
    # Response capture (for table columns): the return annotation's model, the
    # list-envelope field holding list[Model] (e.g. "data"), and the ITEM model's
    # fields (envelope unwrapped; == the return model's own fields when not a list op).
    return_model: str | None = None
    items_field: str | None = None
    response_fields: list[FieldInfo] = []
```

- [ ] **Step 4: Capture the return annotation in introspect.py**

Add to `src/phantasos/generator/cli/introspect.py` (after `_union_members`):

```python
def _response_info(tp: object) -> tuple[str | None, str | None, list[FieldInfo]]:
    """(return_model, items_field, item_fields) from a return annotation.

    A return model with a list[Model] field is a list envelope: items_field is
    that field's name and the fields are the inner model's. Otherwise the return
    model itself is the item.
    """
    base = _unwrap_optional(tp)
    if not (isinstance(base, type) and issubclass(base, BaseModel)):
        return None, None, []
    for fname, field in base.model_fields.items():
        inner = _unwrap_optional(field.annotation)
        if get_origin(inner) in (list, set):
            args = get_args(inner)
            item = _unwrap_optional(args[0]) if args else None
            if isinstance(item, type) and issubclass(item, BaseModel):
                return base.__name__, fname, _model_fields(item)
    return base.__name__, None, _model_fields(base)
```

In `_introspect`, after `summary, description = _docstring_parts(callable_fn)` add:

```python
            return_model, items_field, response_fields = _response_info(
                hints.get("return")
            )
```

and extend the `OperationInfo(...)` construction:

```python
                OperationInfo(
                    resource=resource,
                    method=method,
                    summary=summary,
                    description=description,
                    params=params,
                    body_fields=body_fields,
                    return_model=return_model,
                    items_field=items_field,
                    response_fields=response_fields,
                )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_introspect.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/inventory.py src/phantasos/generator/cli/introspect.py tests/test_cli_introspect.py
git commit -m "feat(cli-gen): introspect response models (return model, items field, item fields)"
```

---

### Task 3: IR — ColumnSpec + Command.columns/items_field

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py`
- Test: `tests/test_cli_ir.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_ir.py`:

```python
def test_command_columns_roundtrip():
    from phantasos.generator.cli.ir import CliIR, ColumnSpec, Command

    cmd = Command(
        verb="show", object="widget", key="show:widget", sdk_resource="widgets",
        items_field="data",
        columns=[ColumnSpec(header="name", path="name"),
                 ColumnSpec(header="OWNER", path="owner.name")],
    )
    ir = CliIR(sdk_package="x", sdk_version="1", commands=[cmd])
    back = CliIR.model_validate_json(ir.model_dump_json())
    assert back.commands[0].items_field == "data"
    assert back.commands[0].columns[1].path == "owner.name"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_ir.py -q`
Expected: FAIL — no `ColumnSpec` / unknown fields.

- [ ] **Step 3: Extend ir.py**

In `src/phantasos/generator/cli/ir.py`, add above `Command`:

```python
class ColumnSpec(BaseModel):
    """One table column: a header + a JMESPath evaluated against each row dict
    (snake_case keys — rows come from model_dump(mode="json") without by_alias)."""

    model_config = ConfigDict(extra="forbid")

    header: str
    path: str
```

and add to `Command` (after `paginated`):

```python
    # list-envelope field holding the rows (e.g. "data"); None when the op
    # returns the item directly
    items_field: str | None = None
    # resolved table columns: cli.yml columns or model-derived defaults
    columns: list[ColumnSpec] = []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_ir.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/ir.py tests/test_cli_ir.py
git commit -m "feat(cli-gen): IR carries ColumnSpec + items_field per command"
```

---

### Task 4: cliconfig — `columns:` section

**Files:**
- Modify: `src/phantasos/generator/cli/cliconfig.py`
- Test: `tests/test_cli_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_config.py` (match the file's existing tmp-yaml pattern):

```python
def test_columns_section_loads(tmp_path):
    from phantasos.generator.cli.cliconfig import ColumnEntry, load_cli_config

    p = tmp_path / "cli.yml"
    p.write_text(
        "columns:\n"
        "  device-group:\n"
        "    - id\n"
        "    - name\n"
        "    - header: MEMBERS\n"
        "      path: \"members[].name\"\n",
        encoding="utf-8",
    )
    cfg = load_cli_config(p)
    entries = cfg.columns["device-group"]
    assert entries[0] == "id"
    assert isinstance(entries[2], ColumnEntry)
    assert entries[2].header == "MEMBERS"
    assert entries[2].path == "members[].name"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_config.py -q`
Expected: FAIL — `CliConfig` forbids extra key `columns`.

- [ ] **Step 3: Extend cliconfig.py**

Add after `VariantMap`:

```python
class ColumnEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: str
    path: str  # JMESPath over the row dict (snake_case keys)
```

and to `CliConfig` (after `variants`):

```python
    # object -> table columns; a bare string is shorthand for header == path
    columns: dict[str, list[str | ColumnEntry]] = {}
```

Also update the module docstring's section list to mention `columns`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/cliconfig.py tests/test_cli_config.py
git commit -m "feat(cli-gen): cli.yml columns: section (per-object table columns)"
```

---

### Task 5: columns.py — defaults heuristic + build-time JMESPath validation

**Files:**
- Create: `src/phantasos/generator/cli/columns.py`
- Modify: `pyproject.toml` (jmespath dep + mypy override)
- Test: `tests/test_cli_columns.py` (new)

- [ ] **Step 1: Add the jmespath dependency**

In `pyproject.toml` `[project] dependencies` (line ~20), add `"jmespath>=1.0",`. In the mypy overrides section (there is an existing override for `ruamel` around line 106), add:

```toml
[[tool.mypy.overrides]]
module = ["jmespath", "jmespath.*"]
ignore_missing_imports = true
```

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv sync --all-extras` (or the repo's usual sync) — jmespath installs.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_cli_columns.py`:

```python
"""Tests for build-time column derivation and cli.yml columns validation."""

import pytest

from phantasos.generator.cli.cliconfig import ColumnEntry
from phantasos.generator.cli.columns import default_columns, resolve_columns
from phantasos.generator.cli.inventory import FieldInfo


def _f(name, kind="scalar", **kw):
    return FieldInfo(name=name, annotation="str", kind=kind, required=False, **kw)


FIELDS = [
    _f("created_at"),
    _f("name"),
    _f("spec", kind="json"),
    _f("id"),
    _f("status", kind="enum", enum_values=["on", "off"]),
    _f("region"),
    _f("zone"),
    _f("weight"),
]


def test_default_columns_prefers_known_names_then_scalars_capped():
    cols = default_columns(FIELDS)
    assert [c.path for c in cols] == [
        "id", "name", "status",          # preferred order first
        "created_at", "region", "zone",  # then declaration order, cap 6
    ]
    assert all(c.header == c.path for c in cols)


def test_default_columns_excludes_json_fields():
    assert "spec" not in [c.path for c in default_columns(FIELDS)]


def test_resolve_columns_string_shorthand_and_entry():
    cols = resolve_columns(
        ["name", ColumnEntry(header="MEMBERS", path="members[].name")],
        FIELDS_WITH_MEMBERS, "device-group",
    )
    assert (cols[0].header, cols[0].path) == ("name", "name")
    assert (cols[1].header, cols[1].path) == ("MEMBERS", "members[].name")


FIELDS_WITH_MEMBERS = [*FIELDS, _f("members", kind="json")]


def test_resolve_columns_rejects_bad_jmespath_syntax():
    with pytest.raises(ValueError, match="invalid JMESPath"):
        resolve_columns(["members[].]"], FIELDS, "device-group")


def test_resolve_columns_rejects_unknown_root_field():
    with pytest.raises(ValueError, match="unknown field 'nope'"):
        resolve_columns(["nope.deeper"], FIELDS, "device-group")


def test_resolve_columns_skips_root_check_when_fields_unknown():
    # No response model introspected -> syntax-only validation
    cols = resolve_columns(["anything.goes"], [], "device-group")
    assert cols[0].path == "anything.goes"


def test_resolve_columns_skips_root_check_for_non_field_roots():
    # function at root: best-effort check must not false-positive
    cols = resolve_columns(["join(', ', tags)"], [*FIELDS, _f("tags")], "x")
    assert cols[0].header == "join(', ', tags)"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_columns.py -q`
Expected: FAIL — `No module named 'phantasos.generator.cli.columns'`.

- [ ] **Step 4: Implement columns.py**

Create `src/phantasos/generator/cli/columns.py`:

```python
"""Table-column resolution: model-derived defaults + cli.yml validation.

Columns are JMESPath expressions evaluated (at CLI runtime) against each row
dict produced by model_dump(mode="json") WITHOUT by_alias — i.e. snake_case
Python field names, which is also what build-time validation checks against.
"""

from __future__ import annotations

import jmespath
from jmespath.exceptions import ParseError

from .cliconfig import ColumnEntry
from .inventory import FieldInfo
from .ir import ColumnSpec

# Identity-ish fields users scan for, in display order.
_PREFERRED = ("id", "name", "type", "status", "state")
_MAX_DEFAULT = 6


def default_columns(fields: list[FieldInfo]) -> list[ColumnSpec]:
    """Preferred names first, then remaining scalar/enum fields in declaration
    order, capped at _MAX_DEFAULT. json-kind (nested) fields are excluded."""
    names = {f.name for f in fields}
    chosen = [n for n in _PREFERRED if n in names]
    for f in fields:
        if len(chosen) >= _MAX_DEFAULT:
            break
        if f.name not in chosen and f.kind in ("scalar", "enum"):
            chosen.append(f.name)
    return [ColumnSpec(header=n, path=n) for n in chosen[:_MAX_DEFAULT]]


def _root_field(node: dict) -> str | None:
    """Leftmost plain field of a parsed JMESPath AST, or None if the root is
    not field-shaped (function, literal, projection of a literal, ...)."""
    while True:
        if node.get("type") == "field":
            return str(node["value"])
        children = node.get("children") or []
        if not children or not isinstance(children[0], dict):
            return None
        node = children[0]


def resolve_columns(
    entries: list[str | ColumnEntry], fields: list[FieldInfo], obj: str
) -> list[ColumnSpec]:
    """Normalize cli.yml column entries; raise ValueError (-> build failure) on
    invalid JMESPath or an unknown root field (best-effort, only when the item
    model's fields are known and the AST root is a plain field)."""
    known = {f.name for f in fields}
    out: list[ColumnSpec] = []
    for e in entries:
        header, path = (e, e) if isinstance(e, str) else (e.header, e.path)
        try:
            parsed = jmespath.compile(path).parsed
        except ParseError as exc:
            raise ValueError(
                f"cli.yml columns.{obj}: invalid JMESPath {path!r}: {exc}"
            ) from exc
        root = _root_field(parsed)
        if known and root is not None and root not in known:
            raise ValueError(
                f"cli.yml columns.{obj}: unknown field {root!r} in {path!r}"
                f" (available: {', '.join(sorted(known))})"
            )
        out.append(ColumnSpec(header=header, path=path))
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_columns.py -q`
Expected: PASS. If `test_resolve_columns_skips_root_check_for_non_field_roots` fails because jmespath's AST shape differs from `_root_field`'s assumption (e.g. the function's first child IS the field `tags` and `tags` is known → passes anyway), inspect `jmespath.compile("join(', ', tags)").parsed` and adjust the test's expression (e.g. use `` "`literal`" ``) — the contract is "non-field roots are skipped", not a specific AST shape.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/columns.py tests/test_cli_columns.py pyproject.toml uv.lock
git commit -m "feat(cli-gen): column defaults heuristic + build-time JMESPath validation"
```

---

### Task 6: build_cli_ir — attach columns + items_field to commands

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_classify.py` (the file already builds inventories from the fakesdk fixture and/or hand-built `OperationInventory`s — reuse its fixture/helpers; shown here with the real fakesdk introspection used elsewhere in the suite):

```python
def test_show_widget_gets_default_columns_and_items_field():
    from pathlib import Path

    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    ir, _ = build_cli_ir(introspect("fakesdk", fixture), CliConfig())
    show = next(c for c in ir.commands if c.key == "show:widget")
    assert show.items_field == "data"           # from list_widgets -> WidgetList
    paths = [c.path for c in show.columns]
    assert paths[:2] == ["id", "name"]          # preferred first
    assert "spec" not in paths                   # nested excluded
    create = next(c for c in ir.commands if c.key == "create:widget")
    assert [c.path for c in create.columns] == paths  # same object, same columns


def test_cli_yml_columns_override_and_validate():
    from pathlib import Path

    import pytest

    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = introspect("fakesdk", fixture)

    cfg = CliConfig(columns={"widget": ["name", "members[].name"]})
    ir, _ = build_cli_ir(inv, cfg)
    show = next(c for c in ir.commands if c.key == "show:widget")
    assert [c.path for c in show.columns] == ["name", "members[].name"]

    with pytest.raises(ValueError, match="unknown field 'nope'"):
        build_cli_ir(inv, CliConfig(columns={"widget": ["nope"]}))

    with pytest.raises(ValueError, match="unknown object"):
        build_cli_ir(inv, CliConfig(columns={"no-such-object": ["id"]}))


def test_no_response_model_means_no_columns():
    from pathlib import Path

    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    ir, _ = build_cli_ir(introspect("fakesdk", fixture), CliConfig())
    gizmo_show = next(c for c in ir.commands if c.key == "show:gizmo")
    assert gizmo_show.columns == []             # gizmos are unannotated
    assert gizmo_show.items_field is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_classify.py -q`
Expected: the three new tests FAIL (`columns == []`, `items_field is None` everywhere, no unknown-object error).

- [ ] **Step 3: Implement the second pass in build_cli_ir**

In `src/phantasos/generator/cli/classify.py`, import the new module:

```python
from .columns import default_columns, resolve_columns
```

At the end of `build_cli_ir`, BEFORE constructing `CliIR(...)`, add:

```python
    # ---- Table columns: attach response shape + resolved columns per command.
    # Representative op per command: prefer the list binding (its envelope gives
    # items_field), else get, else any binding with a response model.
    ops_by_key = {f"{op.resource}.{op.method}": op for op in inv.operations}
    rank = {"list": 0, "get": 1}
    for cmd in groups.values():
        op = next(
            (o for b in sorted(cmd.bindings,
                               key=lambda b: rank.get(b.sub_verb, 9))
             if (o := ops_by_key.get(f"{cmd.sdk_resource}.{b.sdk_method}"))
             and o.response_fields),
            None,
        )
        if op is None:
            continue
        cmd.items_field = op.items_field
        entries = cfg.columns.get(cmd.object)
        if entries is not None:
            cmd.columns = resolve_columns(entries, op.response_fields, cmd.object)
        else:
            cmd.columns = default_columns(op.response_fields)
    unknown_objects = set(cfg.columns) - {c.object for c in groups.values()}
    if unknown_objects:
        raise ValueError(
            "cli.yml columns: unknown object(s): "
            + ", ".join(sorted(unknown_objects))
        )
```

Note the walrus `(o := ...)` inside a generator — if ruff/mypy complains in this codebase's config, rewrite as an explicit loop; behavior is what matters.

- [ ] **Step 4: Run the full suite**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q`
Expected: all PASS (new tests included; ir.json snapshots elsewhere tolerate the additive fields because the IR is serialized from models, not golden-filed — if a golden/byte-identity test fails, update it deliberately and say so in the commit).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): build_cli_ir resolves table columns + items_field into the IR"
```

---

### Task 7: emitted output.py — table renderer (rows, JMESPath cells, previews, parsing)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/output.py.jinja`
- Modify: `src/phantasos/generator/cli/scaffold_context.py` (`_CLI_DEPS`)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_emitted.py`:

```python
def _row(i):
    return {
        "id": f"w{i}", "name": f"widget-{i}", "priority": i, "enabled": True,
        "tags": ["a", "b", "c", "d", "e"],
        "spec": {"x": 1},
        "members": [{"name": "alice"}, {"name": "bob"}, {"name": "carol"},
                    {"name": "dave"}],
    }


def test_table_unwraps_list_envelope_and_uses_default_columns(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    envelope = {"page_info": {"cursor": None}, "data": [_row(1), _row(2)]}
    out.render(envelope, fmt="table",
               default_columns=[("id", "id"), ("name", "name")],
               items_field="data")
    text = capsys.readouterr().out
    assert "w1" in text and "widget-2" in text     # rows, not the envelope
    assert "page_info" not in text


def test_table_jmespath_columns_and_joined_preview(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render([_row(1)], fmt="table",
               columns=["name", "MEMBERS=members[].name", "tags"])
    text = capsys.readouterr().out
    assert "MEMBERS" in text
    assert "alice, bob, carol, +1 more" in text    # list-of-dicts preview via path
    assert "a, b, c, +2 more" in text              # scalar list preview


def test_table_cell_rendering_rules(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    row = {"id": "x", "gone": None, "flag": True, "nest": {"a": 1},
           "objs": [{"k": 1}, {"k": 2}]}
    out.render([row], fmt="table",
               columns=["id", "gone", "flag", "nest", "objs"])
    text = capsys.readouterr().out
    assert "true" in text                          # bools lowercase
    assert '{"a":1}' in text                       # dict -> compact json
    assert "2 items" in text                       # dicts w/o name/id -> count


def test_table_heuristic_fallback_when_no_columns(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    rows = [{"created": "t", "name": "n1", "id": "i1", "deep": {"x": 1},
             "a": 1, "b": 2, "c": 3, "d": 4}]
    out.render(rows, fmt="table")                  # no columns at all
    text = capsys.readouterr().out
    assert "id" in text and "name" in text         # preferred first
    assert "deep" not in text                      # nested excluded
    # cap 6: id, name, created, a, b, c -> "d" doesn't fit
    assert " d " not in text


def test_columns_split_and_header_parsing(emitted):
    out = importlib.import_module("fakesdk_cli._generated.output")
    specs = out.parse_columns(["id,OWNER=owner.name", "F=join(', ', tags)"])
    assert specs == [("id", "id"), ("OWNER", "owner.name"),
                     ("F", "join(', ', tags)")]    # comma inside () not split


def test_table_invalid_runtime_columns_exits_cleanly(emitted, capsys):
    import pytest

    out = importlib.import_module("fakesdk_cli._generated.output")
    with pytest.raises(SystemExit):
        out.render([{"id": "x"}], fmt="table", columns=["bad[expr"])
    assert "invalid --columns" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "table or columns"`
Expected: FAIL — `render()` doesn't accept the new kwargs; `parse_columns` missing.

- [ ] **Step 3: Implement in output.py.jinja**

In `src/phantasos/generator/cli/templates/_generated/output.py.jinja`:

Add imports: `import re` (top, with the others) and `import jmespath` (third-party block, before `import yaml`).

Replace `def render(...)` and `_render_table` with:

```python
def render(
    result: Any,
    fmt: str = "json",
    *,
    columns: list[str] | None = None,
    default_columns: list[tuple[str, str]] | None = None,
    items_field: str | None = None,
) -> None:
    if result is None:
        return  # empty success (e.g. delete / HTTP 204) — print nothing
    data = _to_data(result)
    if fmt == "yaml":
        print(yaml.safe_dump(data, sort_keys=False, default_flow_style=False), end="")
        return
    if fmt == "table":
        _render_table(data, columns=columns, default_columns=default_columns,
                      items_field=items_field)
        return
    _console.print_json(data=data)  # default: Rich-formatted JSON
```

Append the table machinery (replacing the old `_render_table` entirely):

```python
# ---- table rendering -------------------------------------------------------

_PREFERRED = ("id", "name", "type", "status", "state")
_MAX_HEURISTIC = 6
_PREVIEW = 3


def _split_columns(value: str) -> list[str]:
    """Split a --columns value on top-level commas (commas inside [], (), {},
    quotes or backticks belong to the JMESPath expression)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in value:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            buf.append(ch)
        elif ch in "[({":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf).strip())
    return [p for p in parts if p]


_HEADER_RE = re.compile(r"^([A-Za-z0-9_ .-]+)=(?!=)")


def parse_columns(values: list[str]) -> list[tuple[str, str]]:
    """[(header, jmespath)] from --columns values; 'HEADER=expr' names a column
    (a lone '=' — '==' comparisons pass through to the expression)."""
    specs: list[tuple[str, str]] = []
    for v in values:
        for part in _split_columns(v):
            m = _HEADER_RE.match(part)
            if m:
                specs.append((m.group(1).strip(), part[m.end():].strip()))
            else:
                specs.append((part, part))
    return specs


def _rows(data: Any, items_field: str | None) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and items_field:
        items = data.get(items_field)
        if isinstance(items, list):
            return items
    return [data]


def _preview(items: list[Any]) -> str:
    if not items:
        return ""
    if all(isinstance(i, dict) for i in items):
        labels = [i.get("name") or i.get("id") for i in items]
        if any(label is None for label in labels):
            return f"{len(items)} items"
        shown = [str(label) for label in labels[:_PREVIEW]]
    else:
        shown = [_cell(i) for i in items[:_PREVIEW]]
    extra = len(items) - _PREVIEW
    return ", ".join(shown) + (f", +{extra} more" if extra > 0 else "")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return _preview(value)
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def _heuristic_columns(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Last-resort columns from the data itself: top-level scalar-ish keys in
    first-seen order, preferred identity fields first, cap _MAX_HEURISTIC."""
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k, v in r.items():
            if k in seen:
                continue
            seen.add(k)
            if isinstance(v, dict):
                continue
            if isinstance(v, list) and any(
                isinstance(i, (dict, list)) for i in v
            ):
                continue
            keys.append(k)
    ordered = [k for k in _PREFERRED if k in keys]
    ordered += [k for k in keys if k not in ordered]
    return [(k, k) for k in ordered[:_MAX_HEURISTIC]]


class _Key:
    """Plain-key getter with the same .search interface as a compiled JMESPath.

    Used for data-derived heuristic columns: raw API keys are not guaranteed to
    be valid JMESPath identifiers, and the heuristic must never exit."""

    def __init__(self, key: str) -> None:
        self.key = key

    def search(self, row: dict[str, Any]) -> Any:
        return row.get(self.key)


def _getters(
    specs: list[tuple[str, str]],
) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for header, path in specs:
        try:
            out.append((header, jmespath.compile(path)))
        except Exception as exc:  # jmespath.exceptions.ParseError and friends
            _err_console.print(f"[bold red]invalid --columns expression[/] "
                               f"{path!r}: {exc}")
            raise SystemExit(2) from exc
    return out


def _render_table(
    data: Any,
    *,
    columns: list[str] | None = None,
    default_columns: list[tuple[str, str]] | None = None,
    items_field: str | None = None,
) -> None:
    rows = [r for r in _rows(data, items_field) if isinstance(r, dict)]
    if not rows:
        _console.print("[dim]no results[/]")
        return
    if columns:
        getters = _getters(parse_columns(columns))
    elif default_columns:
        getters = _getters(list(default_columns))
    else:
        # heuristic columns come from the data itself: plain key lookup, never
        # jmespath-compiled (arbitrary keys may not be valid JMESPath)
        getters = [(h, _Key(p)) for h, p in _heuristic_columns(rows)]
    table = Table(*[h for h, _ in getters])
    for r in rows:
        table.add_row(*[_cell(g.search(r)) for _, g in getters])
    _console.print(table)
```

(Note `_getters` compiles cli.yml-sourced default columns too — they were validated at build time, so a failure here is unreachable in practice, but the unified path keeps the code small.)

- [ ] **Step 4: Add jmespath to the emitted CLI's dependencies**

In `src/phantasos/generator/cli/scaffold_context.py`:

```python
_CLI_DEPS = [
    "typer>=0.12", "rich>=13", "pyyaml>=6", "python-dotenv>=1.0", "jmespath>=1.0",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py tests/test_cli_scaffold.py -q`
Expected: PASS, including the pre-existing `test_output_formats` (its table assertion still holds via the heuristic path). If `test_cli_scaffold.py` asserts the exact dependency list, update that assertion to include jmespath.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/output.py.jinja src/phantasos/generator/cli/scaffold_context.py tests/test_cli_emitted.py tests/test_cli_scaffold.py
git commit -m "feat(cli-gen): JMESPath table renderer (envelope rows, previews, --columns parsing)"
```

---

### Task 8: --columns flag plumbing (commands template + runtime)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/commands.py.jinja`
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (`_RESERVED`)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli_emitted.py` (reuse the existing `_fake_client` recorder helper and CliRunner patterns in this file):

```python
def test_columns_flag_implies_table_and_renders_curated(emitted, monkeypatch, capsys):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    models = importlib.import_module("fakesdk.models")

    page = models.WidgetList(
        data=[models.Widget(id="w1", name="alpha", tags=["t1", "t2"]),
              models.Widget(id="w2", name="beta")]
    )

    class _W:
        def list_widgets(self, **kw):
            return page

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--columns", "name,id"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output and "w2" in res.output
    assert "page_info" not in res.output            # envelope unwrapped
    assert "{" not in res.output                     # table, not json


def test_show_without_columns_uses_ir_default_columns(emitted, monkeypatch):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    models = importlib.import_module("fakesdk.models")

    page = models.WidgetList(data=[models.Widget(id="w1", name="alpha")])

    class _W:
        def list_widgets(self, **kw):
            return page

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--output", "table"])
    assert res.exit_code == 0, res.output
    # ir default columns put id/name first and exclude the nested spec field
    assert "id" in res.output and "name" in res.output
    assert "spec" not in res.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "columns_flag or ir_default"`
Expected: FAIL — `--columns` is not a recognized option / envelope row rendered.

- [ ] **Step 3: Implement the plumbing**

`src/phantasos/generator/cli/render_cli.py` — extend the reserved names:

```python
_RESERVED = {"output", "all_", "dry_run", "verbose", "self", "columns"}
```

`src/phantasos/generator/cli/templates/_generated/commands.py.jinja` — add a `--columns` option to the generated signature (after the `output` line):

```jinja
    output: str = typer.Option("json", "--output"),
    columns: list[str] | None = typer.Option(
        None,
        "--columns",
        help=(
            "Table columns as comma-separated JMESPath expressions"
            " (implies --output table). 'HEADER=expr' names a column."
        ),
    ),
```

and pass it through in the `_rt.run(` call:

```jinja
        output=output, columns=columns, paginate_all=all_, dry_run=dry_run, verbose=verbose,
```

`src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — extend `run`'s signature:

```python
def run(key: str, *, path: dict[str, Any], body: dict[str, Any],
        query: dict[str, Any], output: str, paginate_all: bool,
        dry_run: bool, verbose: bool,
        columns: list[str] | None = None) -> None:
```

right after `cmd = _commands()[key]` add:

```python
    if columns:
        output = "table"  # --columns implies table rendering
```

and replace the render call:

```python
        _output.render(
            result, fmt=output, columns=columns,
            default_columns=[(c.header, c.path) for c in cmd.columns],
            items_field=cmd.items_field,
        )
```

- [ ] **Step 4: Run the full suite**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q`
Expected: all PASS. The existing CliRunner tests pass `output="json"` paths untouched; `--all` pagination returns a plain list — `_rows` passes it straight through.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/commands.py.jinja src/phantasos/generator/cli/templates/_generated/runtime.py.jinja src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): --columns flag (JMESPath, implies table) wired through runtime"
```

---

### Task 9: discover stub pre-fills columns

**Files:**
- Modify: `src/phantasos/generator/cli/discover.py`
- Test: `tests/test_cli_discover.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli_discover.py`:

```python
def test_stub_prefills_columns_from_defaults():
    from phantasos.generator.cli.discover import render_stub
    from phantasos.generator.cli.ir import CliIR, ColumnSpec, Command

    ir = CliIR(sdk_package="x", sdk_version="1", commands=[
        Command(verb="show", object="widget", key="show:widget",
                sdk_resource="widgets",
                columns=[ColumnSpec(header="id", path="id"),
                         ColumnSpec(header="name", path="name")]),
        Command(verb="create", object="widget", key="create:widget",
                sdk_resource="widgets",
                columns=[ColumnSpec(header="id", path="id"),
                         ColumnSpec(header="name", path="name")]),
        Command(verb="show", object="gizmo", key="show:gizmo",
                sdk_resource="gizmos"),  # no columns -> omitted
    ])
    stub = render_stub(ir, [])
    assert "columns:" in stub
    assert "widget: [id, name]" in stub
    assert stub.count("widget:") == 1          # deduped across verbs
    assert "gizmo:" not in stub
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_discover.py -q`
Expected: FAIL — stub has no `columns:` section.

- [ ] **Step 3: Implement in render_stub**

In `src/phantasos/generator/cli/discover.py`, inside `render_stub` before `lines.append("hide: []")`:

```python
    col_lines: list[str] = []
    seen_objects: set[str] = set()
    for c in sorted(ir.commands, key=lambda c: c.object):
        if c.object in seen_objects or not c.columns:
            continue
        seen_objects.add(c.object)
        col_lines.append(
            f"  {c.object}: [{', '.join(s.path for s in c.columns)}]"
        )
    if col_lines:
        lines.append("# Table columns per object (JMESPath; model-derived"
                     " defaults shown — edit to curate).")
        lines.append("columns:")
        lines.extend(col_lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_discover.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/discover.py tests/test_cli_discover.py
git commit -m "feat(cli-gen): discover stub pre-fills columns: with model-derived defaults"
```

---

### Task 10: real-SDK capstone — author prisma-browser columns + gated e2e

**Files:**
- Modify: `products/prisma-browser/cli.yml`
- Test: `tests/test_cli_emitted_real.py`

- [ ] **Step 1: Inspect the real models to pick column fields**

Run (adjust to taste):
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run python -c "
import sys; sys.path.insert(0, '/home/ubuntu/git/prisma-browser-sdk')
from prisma_browser.models.device_group import DeviceGroup
from prisma_browser.models.application_item import ApplicationItem
print('DeviceGroup:', list(DeviceGroup.model_fields))
print('ApplicationItem:', list(ApplicationItem.model_fields))
"
```
(If `ApplicationItem` is not the list item model, find it via `ListApplications200Response.model_fields` — whichever field is `List[X]`, use X.) Use REAL snake_case field names from this output in the next step; do not guess.

- [ ] **Step 2: Author columns in products/prisma-browser/cli.yml**

Add a `columns:` section curating 2 objects to start (device-group, application), using the field names verified in Step 1 — e.g. (ILLUSTRATIVE, replace with verified names):

```yaml
columns:
  device-group:
    - id
    - name
    - platform
    - created_at
  application:
    - id
    - name
    - type
```

- [ ] **Step 3: Extend the gated real-SDK test**

Append to `tests/test_cli_emitted_real.py` (match its existing gating/skip marker and build fixture — it already builds the real IR/CLI):

```python
def test_real_ir_carries_columns(real_ir):  # reuse the file's real-IR fixture name
    show_dg = next(c for c in real_ir.commands if c.key == "show:device-group")
    assert [c.path for c in show_dg.columns][:2] == ["id", "name"]
    assert show_dg.items_field == "data"
    # every show command with a response model got SOME columns
    shows = [c for c in real_ir.commands if c.verb == "show"]
    assert any(c.columns for c in shows)
```

- [ ] **Step 4: Run the gated tests + a real build**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted_real.py -q`
Expected: PASS (or SKIP if the sibling SDK is absent — then run where it's present; this plan's environment has it).

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser`
Expected: clean build, 0 unmapped; spot-check `../prisma_browser-cli/.../_generated/ir.json` contains `"columns"` entries.

- [ ] **Step 5: Commit**

```bash
git add products/prisma-browser/cli.yml tests/test_cli_emitted_real.py
git commit -m "feat(cli-gen): curated table columns for prisma-browser + real-SDK columns e2e"
```

---

### Task 11: spec sync + lint/type gate

**Files:**
- Modify: `docs/superpowers/specs/2026-06-09-cli-generator-design.md`

- [ ] **Step 1: Append a "Table output & columns" section to the spec**

Document (concisely, matching the spec's style): build-time response introspection; `columns:` in cli.yml (JMESPath, string-or-{header,path}, build-fails-on-invalid); model-derived defaults (preferred names, scalar/enum, cap 6); `--columns` runtime override implying table; joined array previews; snake_case row keys; discover stub pre-fill.

- [ ] **Step 2: Run the full gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run nox -s gate` (or the repo's lint+type+test sessions: `uv run ruff check . && uv run mypy src/ && uv run pytest -q` per noxfile)
Expected: clean. Fix anything it flags before committing.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-09-cli-generator-design.md
git commit -m "docs(spec): table columns design (cli.yml columns, defaults, --columns)"
```

---

## Out of scope (explicitly)

- `-o wide` (rejected by user — `--columns` is the only override).
- Changing the default output format (`json` stays the default; making `show` default to table is a separate UX decision — flagged to the user, not part of this plan).
- Vertical key/value panel for single-item `show --id`.
- Truncation/ellipsis of long cell values (Rich's table already wraps).
- Column sets per *command* (they are per *object*).

## Known risks / notes for the implementer

- **jmespath AST walking** (`_root_field`) is best-effort by design; when in doubt it skips the root-field check (syntax is always checked). Never let it raise.
- **`cmd.columns` is per-object-shared** only by construction (every command of an object resolves the same cli.yml entry or the same item model); there is no cross-command copy step.
- If any **byte-identity/golden test** over emitted files exists and fails (the SDK-scaffold one from Phase 3g is about the SDK pyproject — should be unaffected), update goldens deliberately and call it out in the commit message.
- The runtime heuristic (`_heuristic_columns`) fires only when the IR carries no columns (unannotated SDK returns) — fakesdk gizmos cover this path.
