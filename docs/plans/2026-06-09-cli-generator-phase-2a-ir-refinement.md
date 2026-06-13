# CLI Generator — Phase 2a: IR Refinement (aggregated command model) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the Phase-1 IR so a user-facing command maps to one-or-more SDK methods (aggregated), capturing everything Phase 2b's emission needs — fixing the gaps the python-pro review found before any templates exist.

**Architecture:** Keep the IR-centric pipeline. A `Command` becomes one entry per `(verb, object, variant)` holding candidate `MethodBinding`s (each with its `sub_verb` and the params that select it) and **all** required path params as flags. `build_cli_ir` groups operations instead of emitting one command per method. `introspect` is hardened (restores `sys.path`, treats `Literal[...]` as an enum, captures path/query flag descriptions). `discover` renders the aggregated commands (no more duplicate rows). No code emission in this phase — everything is still verified through `phantasos cli discover`.

**Tech Stack:** Python 3.11–3.14, Pydantic v2, `inspect` + `typing.get_type_hints`, pytest. Test runner: `uv run pytest`.

**Spec:** `docs/specs/2026-06-09-cli-generator-design.md` (see the updated "The `CliIR`" section: `MethodBinding`, `Command.key`, `Command.bindings`, all-required-path-params). **Builds on:** Phase 1 (committed on branch `cli-generator`).

---

## Environment note

The repo `.venv` may be stale / on a filesystem that can't hold symlinks. Use a writable env dir for all commands:

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv   # then `uv run ...` works
```

All `uv run` commands below assume this is exported (or prefix each command with it). Repo root: `/home/ubuntu/git/phantasos`, branch `cli-generator`.

---

## File structure (this phase)

- Modify: `tests/fixtures/fakesdk/fakesdk/{models,api}.py` — add a `Literal` field and an `Annotated`-described path param so the introspect changes are testable.
- Modify: `src/phantasos/generator/cli/introspect.py` — restore `sys.path`; `Literal[...]` → enum; `include_extras=True` + capture param descriptions.
- Modify: `src/phantasos/generator/cli/classify.py` — `Classification.sub_verb`; `build_cli_ir` rewritten to aggregate.
- Modify: `src/phantasos/generator/cli/ir.py` — add `MethodBinding`, `SubVerb`; `Command` gains `key`/`bindings`, drops `sdk_method`.
- Modify: `src/phantasos/generator/cli/discover.py` — render aggregated commands.
- Modify: `tests/test_cli_*.py` — extend/adjust.

---

## Task 1: Extend the fixture for the introspect changes

Add a `Literal` field and an `Annotated`-described path param so Tasks 2's behaviors are testable. Existing tests assert fields by name, so additions won't break them.

**Files:**
- Modify: `tests/fixtures/fakesdk/fakesdk/models.py`
- Modify: `tests/fixtures/fakesdk/fakesdk/api.py`

- [ ] **Step 1: Add a `Literal` field to `WidgetInput`**

In `tests/fixtures/fakesdk/fakesdk/models.py`, add `from typing import Literal` to the imports, and add one field to `WidgetInput` (after `spec`):

```python
    mode: Literal["fast", "slow"] = "fast"  # inline enum (Literal, not an Enum class)
```

- [ ] **Step 2: Add an `Annotated`-described path param to `get_widget_by_id`**

In `tests/fixtures/fakesdk/fakesdk/api.py`, add `from typing import Annotated` and `from pydantic import Field` to the imports, and change `get_widget_by_id`'s `id` param to carry a description:

```python
    def get_widget_by_id(
        self,
        id: Annotated[str, Field(description="The widget id.")],
        configuration_version: str | None = None,
    ):
        """Get a widget by id."""
```

- [ ] **Step 3: Verify the fixture still imports and existing tests still pass**

Run: `uv run pytest tests/test_cli_introspect.py -v`
Expected: still 6 passed (the additions don't break existing assertions).

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/fakesdk
git commit -m "test(cli-gen): fixture gains a Literal field + Annotated-described param"
```

---

## Task 2: Harden introspect (sys.path, Literal enums, param descriptions)

**Files:**
- Modify: `src/phantasos/generator/cli/introspect.py`
- Test: `tests/test_cli_introspect.py`

- [ ] **Step 1: Write the failing tests** (append; put new test functions at the end, no new imports needed):

```python
def test_sys_path_restored_after_introspect():
    import sys
    before = list(sys.path)
    introspect("fakesdk", FIXTURE)
    # introspect must not leave the SDK path lingering on sys.path
    assert sys.path == before


def test_literal_field_is_enum(inv):
    op = _op(inv, "widgets", "create_widget")
    fields = {f.name: f for f in op.body_fields["WidgetInput"]}
    assert fields["mode"].kind == "enum"
    assert fields["mode"].enum_values == ["fast", "slow"]


def test_path_param_description_captured(inv):
    op = _op(inv, "widgets", "get_widget_by_id")
    id_param = next(p for p in op.params if p.name == "id")
    assert id_param.description == "The widget id."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_introspect.py -k "sys_path or literal or description" -v`
Expected: FAIL (sys.path leaks; `mode` kind is "json"; description is "").

- [ ] **Step 3: Implement the three changes in `introspect.py`**

(a) **Literal as enum** — update `_enum_values` to also handle `Literal`, and `_field_kind` to detect it. Add `Literal` to the `typing` imports (`from typing import Literal, Union, get_args, get_origin`). Replace `_enum_values`:

```python
def _enum_values(tp) -> list[str] | None:
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return [str(m.value) for m in tp]
    if get_origin(tp) is Literal:
        return [str(a) for a in get_args(tp)]
    return None
```

(b) **Capture param descriptions via `include_extras=True`** — peel `Annotated` and read a pydantic `Field` description if present. Add a helper and use it. First add imports at top: `from typing import Annotated` is not needed (use `get_origin`/`get_args`); add `from pydantic.fields import FieldInfo as _PydFieldInfo` is not needed either — instead inspect the metadata generically. Add this helper near `_unwrap_optional`:

```python
def _annotated_description(tp) -> str:
    """Extract a description from Annotated[..., Field(description=...)] metadata."""
    if get_origin(tp) is not None and hasattr(tp, "__metadata__"):
        for meta in tp.__metadata__:
            desc = getattr(meta, "description", None)
            if desc:
                return str(desc)
    return ""
```

Update `_unwrap_optional` to also peel `Annotated` so kind detection still works on annotated types:

```python
def _unwrap_optional(tp):
    """Return the underlying type, peeling Annotated[...] and Optional[X]."""
    if get_origin(tp) is not None and hasattr(tp, "__metadata__"):
        tp = get_args(tp)[0]
    if get_origin(tp) in (Union, UnionType):
        non_none = [a for a in get_args(tp) if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap_optional(non_none[0])
    return tp
```

Change the hints call in `introspect` to keep extras, and set the param description. Update the line `hints = typing.get_type_hints(fn, include_extras=False)` to `include_extras=True`, and where `ParamInfo(...)` is built, add `description=_annotated_description(tp)`:

```python
                tp = hints.get(pname, p.annotation)
                base = _unwrap_optional(tp)
                ...
                info = ParamInfo(
                    name=pname,
                    annotation=str(tp),
                    location=location,
                    required=required,
                    default=None if required else p.default,
                    description=_annotated_description(tp),
                    enum_values=_enum_values(base),
                )
```

(c) **Restore `sys.path`** — wrap the path insertion so it's removed in a `finally`. Replace the top of `introspect`:

```python
def introspect(package: str, sdk_path: Path) -> OperationInventory:
    added = str(sdk_path) not in sys.path
    if added:
        sys.path.insert(0, str(sdk_path))
    try:
        return _introspect(package, sdk_path)
    finally:
        if added and str(sdk_path) in sys.path:
            sys.path.remove(str(sdk_path))
```

Move the existing body (from `pkg = importlib.import_module(...)` through the `return OperationInventory(...)`) into a new private `def _introspect(package: str, sdk_path: Path) -> OperationInventory:` and remove the now-duplicated `sys.path.insert` guard from it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_introspect.py -v`
Expected: PASS (9 passed — 6 original + 3 new). The `_model_fields` path already reads `field.annotation` (pydantic v2 strips `Annotated`), so `mode` resolves to `Literal[...]` and `_enum_values` now returns its args.

- [ ] **Step 5: Lint, type-check, full suite**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator/cli/introspect.py && uv run pytest tests/ -q`
Expected: clean; all pass.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/introspect.py tests/test_cli_introspect.py
git commit -m "feat(cli-gen): introspect handles Literal enums, captures descriptions, restores sys.path"
```

---

## Task 3: `Classification.sub_verb`

The classifier must report the fine-grained operation (create/patch/update/get/list/delete/bulk_*) so `build_cli_ir` can build per-binding dispatch metadata.

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py` (add the `SubVerb` type)
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Add the `SubVerb` type to `ir.py`**

In `src/phantasos/generator/cli/ir.py`, after the `Verb` definition, add:

```python
SubVerb = Literal[
    "create", "patch", "update", "get", "list", "delete", "bulk_create", "bulk_delete"
]
```

- [ ] **Step 2: Write the failing tests** (append to `tests/test_cli_classify.py`; the `classify_name` import already exists at top):

```python
@pytest.mark.parametrize(
    "method,sub_verb",
    [
        ("create_application", "create"),
        ("patch_application_by_type_and_id", "patch"),
        ("update_device_group", "update"),
        ("get_application_by_id", "get"),
        ("list_applications", "list"),
        ("delete_application_by_id", "delete"),
        ("bulk_create_applications", "bulk_create"),
        ("bulk_delete_applications", "bulk_delete"),
    ],
)
def test_classify_sub_verb(method, sub_verb):
    c = classify_name(method)
    assert c is not None
    assert c.sub_verb == sub_verb
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_classify.py -k sub_verb -v`
Expected: FAIL (`Classification` has no `sub_verb`).

- [ ] **Step 4: Implement** — change `_VERB_PREFIXES` to also carry the sub-verb, add `sub_verb` to `Classification`, and set it in `classify_name`. In `classify.py`:

Update the import: `from .ir import SubVerb, Verb` (merge with existing `.ir` import line). Replace `_VERB_PREFIXES` and `Classification` and the prefix loop in `classify_name`:

```python
# (prefix, verb, sub_verb) — ORDER MATTERS: longer/compound prefixes first.
_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("bulk_create_", "set", "bulk_create"),
    ("bulk_delete_", "del", "bulk_delete"),
    ("create_", "set", "create"),
    ("update_", "set", "update"),
    ("patch_", "set", "patch"),
    ("delete_", "del", "delete"),
    ("get_", "show", "get"),
    ("list_", "show", "list"),
]


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verb: Verb
    sub_verb: SubVerb
    object: str  # kebab-case noun
```

And in `classify_name`, the loop body:

```python
    for prefix, verb, sub_verb in _VERB_PREFIXES:
        if method.startswith(prefix):
            noun = _strip_id_suffix(method[len(prefix):])
            noun = _singularize(noun)
            return Classification(verb=verb, sub_verb=sub_verb, object=noun.replace("_", "-"))
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS (all prior cases + 8 new sub_verb cases). The prior `test_classify_verb_and_noun` cases still pass (verb/object unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/ir.py src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): classifier reports sub_verb (create/patch/get/list/...)"
```

---

## Task 4: Aggregated IR models (`MethodBinding`, `Command.key`/`bindings`)

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py`
- Test: `tests/test_cli_ir.py`

- [ ] **Step 1: Write the failing test** (replace the body of `test_command_and_ir_roundtrip` in `tests/test_cli_ir.py` and add one — update the import line to include `MethodBinding`):

```python
# update the import at top of tests/test_cli_ir.py:
from phantasos.generator.cli.ir import CliIR, Command, Flag, MethodBinding


def test_command_with_bindings_roundtrip():
    cmd = Command(
        verb="set", object="application", variant=None, key="set:application",
        sdk_resource="applications",
        bindings=[
            MethodBinding(sdk_method="create_application", sub_verb="create", requires=[]),
            MethodBinding(sdk_method="patch_application_by_type_and_id", sub_verb="patch",
                          requires=["type", "id"]),
        ],
        path_params=[Flag(name="--id", param="id", py_type="str", kind="id", required=False)],
        body_flags=[Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)],
    )
    ir = CliIR(sdk_package="fakesdk", sdk_version="9.9.9", commands=[cmd])
    assert ir.commands[0].key == "set:application"
    assert [b.sub_verb for b in ir.commands[0].bindings] == ["create", "patch"]
    assert CliIR.model_validate_json(ir.model_dump_json()) == ir
```

Keep `test_flag_defaults` as-is. Remove the old `test_command_and_ir_roundtrip` (it referenced the removed `sdk_method` field).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_ir.py -v`
Expected: FAIL (`MethodBinding` undefined; `Command` has `sdk_method`/no `key`/no `bindings`).

- [ ] **Step 3: Implement** — in `src/phantasos/generator/cli/ir.py`, add `MethodBinding` and update `Command`. Replace the `Command` class and add `MethodBinding` before it:

```python
class MethodBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sdk_method: str               # e.g. "create_application"
    sub_verb: SubVerb
    requires: list[str] = []      # required path-param names that select this binding at runtime


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verb: Verb
    object: str                   # kebab-case noun, e.g. "application"
    variant: str | None = None    # union variant subcommand, if any
    key: str                      # canonical "verb:object[:variant]"
    sdk_resource: str             # facade attribute, e.g. "applications"
    bindings: list[MethodBinding] = []  # candidate SDK methods; runtime dispatch picks one by args
    path_params: list[Flag] = []  # ALL required path params (id + discriminators like --type)
    body_flags: list[Flag] = []
    query_flags: list[Flag] = []
    summary: str = ""
    description: str = ""
    paginated: bool = False
```

(`ConfigDict` and `SubVerb` are already imported/defined in this module from earlier tasks.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_ir.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/ir.py tests/test_cli_ir.py
git commit -m "feat(cli-gen): aggregated Command model (bindings + key)"
```

---

## Task 5: Rewrite `build_cli_ir` to aggregate by (verb, object, variant)

This is the core of Phase 2a. Group operations into one `Command` per `(verb, object, variant)`, collecting `bindings`, the union of `body_flags`, and **all** required path params (id + discriminators) as flags.

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py`
- Test: `tests/test_cli_classify.py`

- [ ] **Step 1: Write the failing test** (append; the imports `build_cli_ir`, `introspect`, `CliConfig`, `VariantMap`, `Path`, `FIXTURE` already exist at top of the file):

```python
def test_build_cli_ir_aggregates_methods():
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
    by_key = {c.key: c for c in ir.commands}

    # one merged `show widget` carrying BOTH get-one and list bindings
    show_widget = by_key["show:widget"]
    sub = {b.sub_verb for b in show_widget.bindings}
    assert sub == {"get", "list"}
    assert show_widget.paginated is True  # has a list binding

    # one merged `set widget` carrying create + patch (no duplicate commands)
    set_widget = by_key["set:widget"]
    assert {b.sub_verb for b in set_widget.bindings} == {"create", "patch"}
    # exactly one command per (verb, object, variant): no duplicate keys
    assert len([c for c in ir.commands if c.key == "set:widget"]) == 1

    # required NON-id path param (type) is emitted as a flag on gizmo's by_type_and_id read
    show_gizmo = by_key["show:gizmo"]
    pp = {f.param for f in show_gizmo.path_params}
    assert "id" in pp and "type" in pp  # both required path params present

    # gizmo create still fans out into variant subcommands with their own keys
    assert "set:gizmo:simple" in by_key
    assert "set:gizmo:complex" in by_key
    assert any(f.name == "--depth" for f in by_key["set:gizmo:complex"].body_flags)

    # binding.requires records the selecting path params
    get_one = next(b for b in show_widget.bindings if b.sub_verb == "get")
    assert get_one.requires == ["id"]
    list_all = next(b for b in show_widget.bindings if b.sub_verb == "list")
    assert list_all.requires == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_classify.py::test_build_cli_ir_aggregates_methods -v`
Expected: FAIL (current `build_cli_ir` emits one command per method with the old shape).

- [ ] **Step 3: Rewrite `build_cli_ir`** in `classify.py`. Replace the existing `build_cli_ir` function (and its `_id_flag`/`_query_flags`/`_body_flags_for` helpers stay, but `_id_flag` is generalized — see below). Update imports to include `MethodBinding` and `Command` and `CliIR` (`from .ir import CliIR, Command, Flag, MethodBinding, Verb` — merge with existing). Add a `_path_flags` helper and a grouping implementation:

```python
def _path_flags(params: list[ParamInfo], id_param: ParamInfo | None) -> list[Flag]:
    """Every required path param becomes a flag: the detected id as kind 'id' named --id;
    other required path params (discriminators like `type`) as enum/scalar flags."""
    flags: list[Flag] = []
    for p in params:
        if p.location != "path":
            continue
        if id_param is not None and p.name == id_param.name:
            flags.append(Flag(name="--id", param=p.name, py_type="str", kind="id",
                              required=False, help=p.description))
        else:
            flags.append(Flag(name=_flag_name(p.name), param=p.name, py_type="str",
                              kind="enum" if p.enum_values else "scalar",
                              required=False, help=p.description, choices=p.enum_values))
    return flags


def _required_path_names(params: list[ParamInfo]) -> list[str]:
    return [p.name for p in params if p.location == "path"]


def _command_key(verb: str, obj: str, variant: str | None) -> str:
    return f"{verb}:{obj}" + (f":{variant}" if variant else "")


def build_cli_ir(inv: OperationInventory, cfg: CliConfig) -> tuple[CliIR, list[str]]:
    # First pass: classify each op into zero-or-more (key, command-seed, binding) rows.
    groups: dict[str, Command] = {}
    unmapped: list[str] = []

    def _emit(verb: str, obj: str, variant: str | None, op: OperationInfo,
              sub_verb: str, body_model: str | None) -> None:
        key = _command_key(verb, obj, variant)
        id_param = detect_id_param(op.params)
        binding = MethodBinding(
            sdk_method=op.method, sub_verb=sub_verb,  # type: ignore[arg-type]
            requires=_required_path_names(op.params),
        )
        cmd = groups.get(key)
        if cmd is None:
            cmd = Command(
                verb=verb, object=obj, variant=variant, key=key,  # type: ignore[arg-type]
                sdk_resource=op.resource,
                path_params=_path_flags(op.params, id_param),
                body_flags=_body_flags_for(op, body_model),
                query_flags=_query_flags(op.params),
                summary=op.summary, description=op.description,
                paginated=(sub_verb == "list"),
            )
            groups[key] = cmd
        else:
            cmd.paginated = cmd.paginated or sub_verb == "list"
            # merge path params (dedup by param name) and body/query flags
            _merge_flags(cmd.path_params, _path_flags(op.params, id_param))
            _merge_flags(cmd.body_flags, _body_flags_for(op, body_model))
            _merge_flags(cmd.query_flags, _query_flags(op.params))
        cmd.bindings.append(binding)

    for op in inv.operations:
        key0 = f"{op.resource}.{op.method}"
        if key0 in cfg.hide:
            continue
        ov = cfg.override.get(key0)
        cls = classify_name(op.method)
        if cls is None and key0 not in cfg.request:
            unmapped.append(key0)
            continue
        if key0 in cfg.request:
            continue  # request-namespace handled in Phase 3
        if cls is None:  # unreachable after the guards; narrows for mypy
            continue
        verb = ov.verb if ov and ov.verb else cls.verb
        obj = ov.object if ov and ov.object else cls.object
        variants = resolve_variants(op, cfg.variants.get(key0))
        if variants:
            for v in variants:
                _emit(verb, obj, v.name, op, cls.sub_verb, v.model)
        else:
            _emit(verb, obj, None, op, cls.sub_verb, None)

    ir = CliIR(sdk_package=inv.sdk_package, sdk_version=inv.sdk_version,
               commands=list(groups.values()))
    return ir, unmapped
```

Add the `_merge_flags` helper (dedup by flag `name`, keep first):

```python
def _merge_flags(target: list[Flag], extra: list[Flag]) -> None:
    seen = {f.name for f in target}
    for f in extra:
        if f.name not in seen:
            target.append(f)
            seen.add(f.name)
```

Notes for the implementer:
- `verb`/`obj` from an override are `str`; `Command.verb` is the `Verb` Literal — the `# type: ignore[arg-type]` on the `Command(...)` and `MethodBinding(...)` constructions is acceptable, OR cast with `cast(Verb, verb)` / `cast(SubVerb, sub_verb)` (import `cast`) for a cleaner result. Prefer `cast`; keep behavior identical.
- The old single-command branch and the old `_id_flag` are replaced by `_path_flags`. If `_id_flag` is now unused, remove it. Do not leave dead code.
- `select_method_for_verb` remains unused/reserved (its TODO comment stays); aggregation supersedes the dedup framing, but leave it for now — Phase 2b decides whether to delete it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_classify.py -v`
Expected: PASS. The earlier `test_build_cli_ir_end_to_end` (Phase 1) asserted the OLD shape (`cmds` keyed by `(verb, object, variant)` tuple and `body_flags`/`path_params`) — UPDATE that test to the aggregated shape: change its command lookup to `by_key = {c.key: c for c in ir.commands}` and assert against `by_key["set:gizmo:complex"].body_flags` etc.; the `thing` id assertion becomes `any(f.kind == "id" for f in by_key["show:thing"].path_params)`. Keep its intent (widget CRUD present, gizmo variant fan-out, thing id, positions unmapped, sdk_version). If any assertion no longer maps cleanly, align it to the aggregated model — do not delete coverage.

- [ ] **Step 5: Lint, type-check, full suite**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator/cli/classify.py && uv run pytest tests/ -q`
Expected: clean; all pass.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/classify.py tests/test_cli_classify.py
git commit -m "feat(cli-gen): build_cli_ir aggregates methods per (verb,object,variant)"
```

---

## Task 6: Aggregated discover output + real-SDK smoke

`render_table` must show one row per command (with its bindings), and the real-SDK smoke must confirm there are **no duplicate command keys**.

**Files:**
- Modify: `src/phantasos/generator/cli/discover.py`
- Test: `tests/test_cli_discover.py`

- [ ] **Step 1: Write the failing tests** (update `test_render_table_lists_commands_and_unmapped` and append a uniqueness check; imports already present):

```python
def test_render_table_lists_commands_and_unmapped():
    ir, unmapped = _ir_and_unmapped()
    table = render_table(ir, unmapped)
    assert "set widget" in table
    assert "show widget" in table
    # bindings are shown for a merged command (get + list under one show)
    assert "get_widget_by_id" in table and "list_widgets" in table
    assert "UNMAPPED" in table
    assert "widgets.update_widget_positions" in table


def test_command_keys_are_unique():
    ir, _ = _ir_and_unmapped()
    keys = [c.key for c in ir.commands]
    assert len(keys) == len(set(keys))  # aggregation produced no duplicate commands
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_discover.py -v`
Expected: FAIL (`render_table` prints `c.sdk_method` which no longer exists; AttributeError).

- [ ] **Step 3: Update `render_table`** in `discover.py` to render bindings instead of the removed `sdk_method`:

```python
def render_table(ir: CliIR, unmapped: list[str]) -> str:
    lines = [f"# {ir.sdk_package} {ir.sdk_version} — {len(ir.commands)} commands"]
    for c in sorted(ir.commands, key=lambda c: c.key):
        target = f"{c.verb} {c.object}" + (f" {c.variant}" if c.variant else "")
        methods = ", ".join(f"{b.sdk_method}" for b in c.bindings)
        lines.append(f"  {target:<40} <- {c.sdk_resource}.[{methods}]")
    if unmapped:
        lines.append(f"\n# UNMAPPED ({len(unmapped)}) — map in cli.yml (request:/override:/hide:)")
        for key in sorted(unmapped):
            lines.append(f"  UNMAPPED  {key}")
    return "\n".join(lines)
```

(`render_stub` is unchanged — it only uses `unmapped`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_discover.py -v`
Expected: PASS. The Phase-1 real-SDK smoke `test_real_sdk_classifies_without_error` still passes; ADD a uniqueness assertion to it: after `ir, unmapped = build_cli_ir(...)`, add `assert len({c.key for c in ir.commands}) == len(ir.commands)` to prove the real SDK now yields no duplicate commands.

- [ ] **Step 5: Lint, type-check, full suite, and eyeball the real output**

Run: `uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator && uv run pytest tests/ -q`
Then: `uv run phantasos cli discover prisma-browser | head -40`
Expected: clean; all pass; the table now shows ONE `set application` / `show application` / `del application` row each, with multiple methods bracketed (e.g. `<- applications.[create_application, patch_application_by_type_and_id, bulk_create_applications]`).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/discover.py tests/test_cli_discover.py
git commit -m "feat(cli-gen): discover renders aggregated commands; no duplicate keys"
```

---

## Self-review (completed during authoring)

- **Coverage of the python-pro must-do-first items:** (A) all required path params emitted as flags → Task 5 `_path_flags` + test asserting `type` present on `show:gizmo`. (B) `(verb,object,variant)` merge with sub-verb discrimination → Tasks 3 (`sub_verb`) + 4 (`MethodBinding`/`bindings`/`key`) + 5 (aggregation) + 6 (uniqueness test). Canonical `Command.key` → Task 4/5. Cheap hardening: `sys.path` try/finally + `Literal` enum + `include_extras=True` descriptions → Task 2. `select_method_for_verb` left reserved (noted, not deleted — Phase 2b decides). Aggregate-in-IR (the confirmed decision) is the whole shape of Task 5.
- **Placeholder scan:** none — every step has complete code.
- **Type consistency:** `SubVerb` (Task 3, in ir.py) used by `MethodBinding` (Task 4) and `build_cli_ir` (Task 5); `MethodBinding`/`Command.key`/`bindings` (Task 4) consumed by Task 5 and rendered by Task 6; `_path_flags`/`_merge_flags`/`_command_key` defined and used within Task 5; `classify_name` returns `sub_verb` (Task 3) consumed in Task 5. The Phase-1 `test_build_cli_ir_end_to_end` is explicitly updated in Task 5 Step 4 (not left asserting the removed `sdk_method`), and `render_table`'s `sdk_method` usage is updated in Task 6.

## Hand-off to Phase 2b (emission)

After 2a: the IR carries everything emission needs — aggregated `Command`s with `bindings` (+ `requires` and `sub_verb` for runtime dispatch), a canonical `key`, all path params as flags (with help text), permissive-enum `choices`, and `paginated`. Phase 2b plans the Jinja templates, the `_generated/`-vs-hand-owned split, `runtime.py` dispatch (using `bindings`/`requires` + `--id`/`--replace`/`--bulk`), `output.py`, `config.py`, `pyproject.toml` emission, the `phantasos cli build` command, and generated-CLI tests. Scope 2b to `set`/`del`/`show`; defer `request`/`load`/`backup` to Phase 3.
