# CLI flag-schema IR deepening + docs progressive-disclosure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the generated-CLI `Flag` IR to carry each complex (`json`-kind) field's nested schema in a deduped model registry, then consume that registry to render progressive-disclosure CLI docs, a useful `[json: <Model>] e.g. {…}` `--help` stop-gap, a real skeleton in the one-line docs invocation, and a debug-adaptive runtime error example.

**Architecture:** A new CLI-side recursion (`cli/modelschema.py`) walks live SDK body models — reusing now-public opmodel primitives — into a deduped `CliIR.models: dict[str, ModelSchema]` registry, setting each json `Flag.model_ref`. A single registry-driven skeleton synthesizer lives in `ir.py` (shipped verbatim to the runtime via the existing `ir.py`→`spec.py` copy), so the generator (docs + `--help` + invocation) and the runtime (error example) produce byte-identical skeletons. Docs render the registry inline as collapsed `pymdownx.details` blocks with `oneOf` tabs.

**Tech Stack:** Python 3.12+, pydantic v2 (`model_fields`/`model_dump_json`/`model_validate_json`), Jinja2 templates, Typer/Rich (emitted CLI), MkDocs + Material (`pymdownx.details`/`tabbed`/`attr_list`), pytest, uv, nox.

**Basis spec:** `docs/specs/2026-06-22-cli-flag-schema-ir-and-docs-design.md` (decisions D1–D13). Research: `docs/research/2026-06-21-cli-payload-helper-ux/`.

## Global Constraints

- **Branch:** `feature/cli-payload-helper`. PR base = `develop`, **squash-merge**, **no version bump** (record under `## [Unreleased]` in `CHANGELOG.md`). Never push to `main`.
- **Test policy (hook-enforced):** behavioral tests run through the **emitted** package (`tests/test_cli_emitted.py` `emitted` fixture). Prefer real deps; **never mock the system under test**. Evidence before assertions — run the command and show real output before claiming pass. Frozen oracles (`.claude/harness.toml` `protected_globs`: `products/*/overrides/tests/test_sdk_crud_live.py*`, `tests/acceptance/**`, `.claude/**`) are human-owned — never edit them. `tests/fixtures/fakesdk/**` is NOT protected (editable).
- **Phase gate:** `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run nox -s gate` must stay green (runs on Stop). Run `uv run nox -s live` before declaring a phase complete (skips without credentials).
- **Venvs on `~/.tmp` (this machine):** `export UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos` for `uv run …`; for venv-backed nox sessions also `export NOX_ENVDIR=$HOME/.tmp/phantasos-nox`. Do NOT force `TMPDIR=$HOME/.tmp` (it trips a width-sensitive config test). `/tmp` is a small tmpfs that hits EDQUOT.
- **Separation of duty:** keep generator/cli logic separate from generator/sdk — duplicate thin logic rather than couple. The `ir.py`→`spec.py` verbatim copy is the established **intra-CLI** drift-free mechanism (not the sdk/cli boundary), so the synthesizer belongs in `ir.py`.
- **Defaults-sync / frozen invariants:** `extra="forbid"` on `Flag`/`ModelField`/`ModelSchema`/`CliIR` — new fields must be declared, not smuggled. Any function added to `ir.py` MUST be import-clean (stdlib + pydantic only) so it survives the copy to the runtime's `spec.py`.
- **After subsystem changes:** update the relevant `.agents/context/` deep-dive narrative and run `uv run nox -s context` (its `-- --check` must pass).
- **Context-docs / synthesizer purity:** the runtime (`spec.py`) imports the synthesizer; it must not import any live-SDK module or generator-only module.

---

## File Structure

**New files**
- `src/phantasos/generator/cli/modelschema.py` — the live-model→registry recursion (`build_model_registry`). CLI-owned; reuses public opmodel primitives.
- `tests/test_cli_modelschema.py` — unit tests for the recursion (synthetic `BaseModel` fixtures: all-optional, nested `oneOf`, `list[Model]`, A→B→A cycle).
- `tests/test_cli_skeleton.py` — unit tests for the `ir.py` synthesizer (pure registry-data → JSON: minimal/full/non-empty/cycle/oneOf).

**Modified files**
- `src/phantasos/generator/opmodel/introspect.py` — promote 5 primitives to public names.
- `src/phantasos/generator/cli/ir.py` — add `ModelField`, `ModelSchema`, `CliIR.models`, `Flag.model_ref`, and the `synth_skeleton` synthesizer.
- `src/phantasos/generator/cli/classify.py` — `build_cli_ir(…, *, models=None)`; `fields_to_flags(…, schema=None)` sets `model_ref`; attach `CliIR.models`.
- `src/phantasos/cli.py` — call `build_model_registry` and pass `models=` (×2 call sites: `cli_discover`, `cli_build`).
- `src/phantasos/generator/cli/render_cli.py` — `_flag_view` injects the `--help` json annotation + minimal skeleton (threaded `models`).
- `src/phantasos/generator/cli/examples.py` — `example_value` renders the minimal skeleton for json flags (threaded `models`).
- `src/phantasos/generator/cli/docs.py` — `_flag_row` attaches the nested `schema` + full-body skeleton for json flags (threaded `models`).
- `src/phantasos/generator/cli/templates/docs/reference_object.md.jinja` — render collapsed `details` + `oneOf` tabs + full-body skeleton.
- `src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja` — add `pymdownx.details`, `attr_list`, `pymdownx.tabbed`.
- `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — registry+synthesizer-driven, debug-adaptive error example.
- `tests/fixtures/fakesdk/fakesdk/models.py` (+ `api.py` if a new op is needed) — add a nested/oneOf/list/cyclic body model so emitted behavioral tests have a real target.
- `tests/conftest.py` (`emit_cli._emit:58`) and `tests/test_cli_emitted.py` (emit fixtures) — pass `models=` into `build_cli_ir`. `tests/test_cli_emitted_real.py` — **optional** (the `models=None` default keeps its skip-guarded real-SDK tests green; update only a site that asserts on registry behavior).
- `.agents/context/*` (cli generator deep-dive), `CHANGELOG.md`.

---

## Task 1: Promote opmodel walking primitives to public

**Files:**
- Modify: `src/phantasos/generator/opmodel/introspect.py`
- Test: `tests/test_cli_introspect.py`

**Interfaces:**
- Produces: public `field_kind`, `unwrap_optional`, `enum_values`, `scalar_type`, `union_members` (same signatures as today's `_`-prefixed versions). The `_`-prefixed names remain as thin aliases so existing internal callers keep working.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_introspect.py`:

```python
def test_public_primitives_exported() -> None:
    # Submodule-direct import — EXACTLY what cli/modelschema.py (Task 4) uses.
    # Do NOT use `from ...opmodel import introspect as I`: opmodel/__init__.py does
    # `from .introspect import introspect`, rebinding the package attribute
    # `opmodel.introspect` to the FUNCTION (shadowing the submodule), so `I.field_kind`
    # would raise AttributeError. The submodule path below is the real contract.
    from phantasos.generator.opmodel.introspect import (
        enum_values,
        field_kind,
        scalar_type,
        union_members,
        unwrap_optional,
    )

    assert field_kind(str) == "scalar"
    assert field_kind(list[str]) == "scalar"
    assert unwrap_optional(str | None) is str
    assert enum_values(int) is None
    assert scalar_type(bool) == "bool"
    assert callable(union_members)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_introspect.py::test_public_primitives_exported -v`
Expected: FAIL with `ImportError: cannot import name 'field_kind' from 'phantasos.generator.opmodel.introspect'`.

- [ ] **Step 3: Add public names (keep `_` aliases)**

In `introspect.py`, rename the five `def _x(...)` to `def x(...)` and add backward-compat aliases immediately after each (or at module bottom). Concretely, change the `def` lines for `_enum_values`, `_unwrap_optional`, `_scalar_type`, `_field_kind`, `_union_members` to public names, update their internal cross-calls (e.g. `_field_kind` calls `_unwrap_optional`/`_enum_values` → call the public names), then append:

```python
# Backward-compatible private aliases (internal callers + tests still import these).
_enum_values = enum_values
_unwrap_optional = unwrap_optional
_scalar_type = scalar_type
_field_kind = field_kind
_union_members = union_members
```

Leave `_model_fields`, `_item_fields`, `_response_info`, `_annotated_description` private (not needed by the CLI registry).

> **Load-bearing aliases — do NOT delete them.** The shim `src/phantasos/generator/cli/introspect.py` re-exports `_enum_values`/`_unwrap_optional` (in its `__all__`), and `src/phantasos/generator/sdk/wrapper.py:30` + `src/phantasos/generator/sdk/examples.py:21` import those private names from that shim. The `_`-aliases keep those SDK-side importers working — they are permanent, not transitional. (Reviewer-confirmed: no caller references the primitives by `introspect._field_kind` attribute access, so adding public names + keeping aliases is sufficient and non-breaking.)

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_introspect.py -v`
Expected: PASS (new test + all existing introspect tests).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/opmodel/introspect.py tests/test_cli_introspect.py
git commit -m "refactor(opmodel): expose public walking primitives for CLI registry recursion"
```

---

## Task 2: IR data model — `ModelField`, `ModelSchema`, `CliIR.models`, `Flag.model_ref`

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py:92-107` (Flag), `:164-177` (CliIR)
- Test: `tests/test_cli_ir.py`

**Interfaces:**
- Produces:
  ```python
  class ModelField(BaseModel):  # extra="forbid"
      name: str
      alias: str
      py_type: str
      kind: FlagKind
      required: bool
      description: str = ""
      enum_values: list[str] | None = None
      default: Any | None = None
      example: Any | None = None
      model_ref: str | None = None        # nested known model → registry key
      model_ref_list: bool = False        # True when the field is list[<model_ref>]
      variant_refs: list[str] | None = None  # inline-union variants → registry keys
  class ModelSchema(BaseModel):  # extra="forbid"
      fields: list[ModelField]
      is_oneof: bool = False              # wrapper model whose fields ARE its variants
  ```
  `Flag.model_ref: str | None = None`. `CliIR.models: dict[str, ModelSchema] = {}`.

> Note: `model_ref_list` is the explicit list-vs-object marker flagged during grilling (D7) — it keeps the synthesizer from parsing `py_type` strings.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_ir.py`:

```python
def test_model_registry_roundtrips() -> None:
    from phantasos.generator.cli.ir import CliIR, ModelField, ModelSchema

    ir = CliIR(
        sdk_package="x",
        sdk_version="1",
        models={
            "Saas": ModelSchema(
                fields=[
                    ModelField(name="access_mode", alias="accessMode", py_type="str",
                               kind="enum", required=True, enum_values=["none", "any"]),
                    ModelField(name="specific", alias="specific", py_type="Specific | None",
                               kind="json", required=False, model_ref="Specific"),
                ]
            )
        },
    )
    back = CliIR.model_validate_json(ir.model_dump_json())
    assert back.models["Saas"].fields[1].model_ref == "Specific"
    assert back.models["Saas"].fields[0].enum_values == ["none", "any"]


def test_flag_carries_model_ref() -> None:
    from phantasos.generator.cli.ir import Flag

    f = Flag(name="--applications", param="applications", py_type="str",
             kind="json", required=False, model_ref="AccessAndDataPostApplications")
    assert f.model_ref == "AccessAndDataPostApplications"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_ir.py::test_model_registry_roundtrips tests/test_cli_ir.py::test_flag_carries_model_ref -v`
Expected: FAIL (`TypeError`/validation: `models`/`model_ref` unknown).

- [ ] **Step 3: Add the models**

In `ir.py`, add `model_ref: str | None = None` to `Flag` (after `choices`). Add `ModelField` and `ModelSchema` classes (place them above `CliIR`). Add `models: dict[str, ModelSchema] = {}` to `CliIR` (after `error_envelope`). Use the exact shapes from **Interfaces** above. Keep `from typing import Any` (already imported).

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_ir.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/ir.py tests/test_cli_ir.py
git commit -m "feat(cli-ir): add deduped model registry (ModelSchema/ModelField) + Flag.model_ref"
```

---

## Task 3: The skeleton synthesizer in `ir.py` (registry-driven, minimal/full)

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py` (add `synth_skeleton` + `_field_value`)
- Test: `tests/test_cli_skeleton.py` (create)

**Interfaces:**
- Consumes: `ModelSchema`/`ModelField`/`CliIR.models` (Task 2).
- Produces:
  ```python
  def synth_skeleton(models: dict[str, ModelSchema], model_name: str | None, *,
                     full: bool) -> Any
  ```
  `full=True` → all fields (docs). `full=False` → required-only + **non-empty guarantee** (one representative field when no required fields). Cycle-broken on a model repeated in the current path (emits `{}`). `list[model]` fields wrap the child in `[…]`. `oneOf` (wrapper `is_oneof` or field `variant_refs`) uses the **first variant**. Leaf value precedence: `example > default > enum_values[0] > type-synth`. **Import-clean** (stdlib + pydantic only). The recursion's `path` accumulator lives in a private `_synth` helper so the public signature stays clean.

  > **`prefer_variant` dropped (YAGNI).** D9's "`showcase_variant` for a top-level `oneOf`" never reaches the synthesizer: a top-level `oneOf` body is pre-split into per-variant commands (e.g. `create:gizmo:simple`), so a body flag's `model_ref` is always a concrete variant, never the wrapper. First-variant is therefore equivalent for every call site; no caller would ever pass a non-default `prefer_variant`. (Spec D9 footnoted accordingly.)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_skeleton.py`:

```python
from phantasos.generator.cli.ir import ModelField, ModelSchema, synth_skeleton


def _mf(name, **kw):
    kw.setdefault("alias", name)
    kw.setdefault("py_type", "str")
    kw.setdefault("kind", "scalar")
    kw.setdefault("required", False)
    return ModelField(name=name, **kw)


REGISTRY = {
    # all-optional object → non-empty guarantee picks first field (saas)
    "Apps": ModelSchema(fields=[
        _mf("saas", alias="saas", kind="json", model_ref="Saas"),
        _mf("private", alias="private", kind="json", model_ref="Priv"),
    ]),
    "Saas": ModelSchema(fields=[
        _mf("access_mode", alias="accessMode", kind="enum", required=True,
            enum_values=["none", "any"]),
        _mf("specific", alias="specific", kind="json", model_ref="Spec"),
    ]),
    "Priv": ModelSchema(fields=[
        _mf("access_mode", alias="accessMode", kind="enum", required=True,
            enum_values=["none"]),
    ]),
    "Spec": ModelSchema(fields=[
        _mf("ids", alias="applicationIds", kind="scalar", py_type="str"),
    ]),
    # list[Model] field
    "Rule": ModelSchema(fields=[
        _mf("matches", alias="matches", kind="json", required=True,
            model_ref="Match", model_ref_list=True),
    ]),
    "Match": ModelSchema(fields=[_mf("url", alias="url", required=True)]),
    # inline oneOf field (variant_refs)
    "Target": ModelSchema(fields=[
        _mf("body", alias="body", kind="json", required=True,
            variant_refs=["VA", "VB"]),
    ]),
    "VA": ModelSchema(fields=[_mf("a", alias="a", required=True)]),
    "VB": ModelSchema(fields=[_mf("b", alias="b", required=True)]),
    # A -> B -> A cycle
    "A": ModelSchema(fields=[_mf("b", alias="b", kind="json", required=True, model_ref="B")]),
    "B": ModelSchema(fields=[_mf("a", alias="a", kind="json", required=True, model_ref="A")]),
}


def test_minimal_non_empty_guarantee() -> None:
    # all-optional Apps → first field saas → its required accessMode
    assert synth_skeleton(REGISTRY, "Apps", full=False) == {"saas": {"accessMode": "none"}}


def test_minimal_required_only_when_required_present() -> None:
    assert synth_skeleton(REGISTRY, "Saas", full=False) == {"accessMode": "none"}


def test_full_includes_optionals_recursively() -> None:
    out = synth_skeleton(REGISTRY, "Saas", full=True)
    assert out == {"accessMode": "none", "specific": {"applicationIds": "string"}}


def test_list_of_model_wraps_in_array() -> None:
    assert synth_skeleton(REGISTRY, "Rule", full=False) == {"matches": [{"url": "string"}]}


def test_inline_oneof_uses_first_variant() -> None:
    assert synth_skeleton(REGISTRY, "Target", full=False) == {"body": {"a": "string"}}


def test_cycle_breaks_to_empty_object() -> None:
    # A -> B -> A: the second A is on the path → {}
    assert synth_skeleton(REGISTRY, "A", full=True) == {"b": {"a": {}}}


def test_unknown_model_is_empty() -> None:
    assert synth_skeleton(REGISTRY, "Nope", full=True) == {}
    assert synth_skeleton(REGISTRY, None, full=True) == {}


def test_value_precedence_example_beats_default_and_synth() -> None:
    reg = {"M": ModelSchema(fields=[_mf("x", required=True, default="dflt", example="ex")])}
    assert synth_skeleton(reg, "M", full=False) == {"x": "ex"}


def test_value_precedence_default_beats_synth() -> None:
    reg = {"M": ModelSchema(fields=[_mf("x", required=True, default="dflt")])}
    assert synth_skeleton(reg, "M", full=False) == {"x": "dflt"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_skeleton.py -v`
Expected: FAIL with `ImportError: cannot import name 'synth_skeleton'`.

- [ ] **Step 3: Implement the synthesizer in `ir.py`**

Add at the bottom of `ir.py` (after `CliIR`), import-clean:

```python
_LEAF_SYNTH: dict[str, Any] = {"str": "string", "int": 0, "float": 0.0, "bool": False}


def synth_skeleton(
    models: dict[str, ModelSchema], model_name: str | None, *, full: bool
) -> Any:
    """Synthesize a JSON skeleton for ``model_name`` from the registry.

    full=True → all fields incl. optionals (docs). full=False → required-only
    with a non-empty guarantee (--help / invocation / runtime default error).
    Cycle-broken on a model repeated in the current path. Public face; the
    ``path`` accumulator lives in the private ``_synth`` helper below.
    """
    return _synth(models, model_name, full=full, path=())


def _synth(
    models: dict[str, ModelSchema], model_name: str | None, *,
    full: bool, path: tuple[str, ...],
) -> Any:
    if model_name is None or model_name not in models or model_name in path:
        return {}
    schema = models[model_name]
    here = (*path, model_name)  # tuple unpack (ruff RUF005), not path + (x,)
    if schema.is_oneof:
        # A top-level oneOf BODY never reaches here (such bodies are pre-split into
        # per-variant commands → a body flag's model is always a concrete variant);
        # this only fires for a nested oneOf wrapper model. Use the first variant.
        return _field_value(models, schema.fields[0], full=full, path=here) if schema.fields else {}
    out: dict[str, Any] = {}
    for mf in schema.fields:
        if not full and not mf.required:
            continue
        out[mf.alias] = _field_value(models, mf, full=full, path=here)
    if not full and not out and schema.fields:
        out[schema.fields[0].alias] = _field_value(models, schema.fields[0], full=full, path=here)
    return out


def _field_value(
    models: dict[str, ModelSchema], mf: ModelField, *, full: bool, path: tuple[str, ...]
) -> Any:
    if mf.variant_refs:
        return _synth(models, mf.variant_refs[0], full=full, path=path)
    if mf.model_ref:
        child = _synth(models, mf.model_ref, full=full, path=path)
        return [child] if mf.model_ref_list else child
    if mf.example is not None:
        return mf.example
    if mf.default is not None:
        return mf.default
    if mf.enum_values:
        return mf.enum_values[0]
    return _LEAF_SYNTH.get(mf.py_type, "string")
```

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_skeleton.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/ir.py tests/test_cli_skeleton.py
git commit -m "feat(cli-ir): registry-driven skeleton synthesizer (minimal/full, non-empty, cycle-safe)"
```

---

## Task 4: The registry builder — `cli/modelschema.py`

**Files:**
- Create: `src/phantasos/generator/cli/modelschema.py`
- Test: `tests/test_cli_modelschema.py` (create)

**Interfaces:**
- Consumes: public opmodel primitives (Task 1); `ModelField`/`ModelSchema` (Task 2); `OperationInventory` (`from .inventory import OperationInventory`).
- Produces:
  ```python
  def build_model_registry(package: str, sdk_path: Path, inv: OperationInventory
                           ) -> dict[str, ModelSchema]
  # plus the unit-testable core, decoupled from SDK import:
  def registry_from_models(roots: list[type[BaseModel]]) -> dict[str, ModelSchema]
  ```
  `registry_from_models` walks each root recursively, emitting every reachable `BaseModel` **once** (deduped by `__name__`), resolving each field to a `ModelField` with `alias` (`f.alias or name`), `kind` (`field_kind`), `model_ref`/`model_ref_list` (nested model / `list[model]`), `variant_refs` (inline union of models), `enum_values`, `default`, `example` (`f.examples[0]` if present), `description`. A `oneOf` wrapper (`union_members(cls)` non-None) becomes `ModelSchema(is_oneof=True, fields=[ModelField(name=variant, model_ref=variant) …])`. `build_model_registry` imports the SDK (sys.path + the body-model classes named in `inv`) and delegates to `registry_from_models`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_modelschema.py`:

```python
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field

from phantasos.generator.cli.modelschema import registry_from_models


class Spec(BaseModel):
    application_ids: Optional[list[str]] = Field(default=None, alias="applicationIds")


class Saas(BaseModel):
    access_mode: str = Field(alias="accessMode")          # required
    specific: Optional[Spec] = None


class Apps(BaseModel):                                     # all-optional
    saas: Optional[Saas] = None


class Match(BaseModel):
    url: str


class Rule(BaseModel):
    matches: list[Match]                                   # list[Model]


class VA(BaseModel):
    a: str


class VB(BaseModel):
    b: str


class Target(BaseModel):
    body: Union[VA, VB]                                    # inline oneOf field


class A(BaseModel):
    b: Optional["B"] = None


class B(BaseModel):
    a: Optional[A] = None


A.model_rebuild()


def test_registry_dedupes_and_resolves_refs() -> None:
    reg = registry_from_models([Apps])
    assert set(reg) == {"Apps", "Saas", "Spec"}
    saas = reg["Saas"]
    assert saas.fields[0].alias == "accessMode" and saas.fields[0].required
    assert saas.fields[1].model_ref == "Spec" and not saas.fields[1].model_ref_list


def test_registry_list_of_model_marks_list() -> None:
    reg = registry_from_models([Rule])
    f = reg["Rule"].fields[0]
    assert f.model_ref == "Match" and f.model_ref_list is True


def test_registry_inline_oneof_sets_variant_refs() -> None:
    reg = registry_from_models([Target])
    f = reg["Target"].fields[0]
    assert f.variant_refs == ["VA", "VB"] and f.model_ref is None
    assert {"VA", "VB"} <= set(reg)


def test_registry_cycle_emits_each_model_once() -> None:
    reg = registry_from_models([A])
    assert set(reg) == {"A", "B"}            # no infinite expansion
    assert reg["A"].fields[0].model_ref == "B"
    assert reg["B"].fields[0].model_ref == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_modelschema.py -v`
Expected: FAIL with `ModuleNotFoundError: ...cli.modelschema`.

- [ ] **Step 3: Implement `cli/modelschema.py`**

```python
"""Walk live SDK body models into the deduped CliIR model registry.

CLI-owned (separation-of-duty): reuses the opmodel walking primitives but emits
the CLI's own ModelField/ModelSchema descriptors. The recursion lives here, not
in opmodel, so the shared FieldInfo/OperationInfo stay untouched (spec D8).
"""

from __future__ import annotations

import importlib
import sys
import typing
from pathlib import Path
from types import UnionType

from pydantic import BaseModel

from ..opmodel.introspect import (
    enum_values,
    field_kind,
    scalar_type,
    union_members,
    unwrap_optional,
)
from .inventory import OperationInventory
from .ir import FlagKind, ModelField, ModelSchema


def _resolve_ref(tp: object) -> tuple[str | None, bool, list[str] | None]:
    """(model_ref, model_ref_list, variant_refs) for a field annotation."""
    base = unwrap_optional(tp)
    origin = typing.get_origin(base)
    if origin in (list, set):
        args = typing.get_args(base)
        inner = unwrap_optional(args[0]) if args else None
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return inner.__name__, True, None
        return None, False, None
    if isinstance(base, type) and issubclass(base, BaseModel):
        # a oneOf wrapper class is still a single model_ref (its variants live in
        # its own ModelSchema); an inline Union[...] of models is variant_refs.
        return base.__name__, False, None
    if origin in (typing.Union, UnionType):
        members = [
            a for a in typing.get_args(base)
            if isinstance(a, type) and issubclass(a, BaseModel)
        ]
        if len(members) >= 2:
            return None, False, [m.__name__ for m in members]
    return None, False, None


def _model_to_schema(cls: type[BaseModel]) -> tuple[ModelSchema, list[type[BaseModel]]]:
    """Build one ModelSchema; return it + the child model classes to recurse into."""
    children: list[type[BaseModel]] = []
    members = union_members(cls)
    if members:
        ns = sys.modules[cls.__module__]
        fields: list[ModelField] = []
        for name in members:
            member_cls = getattr(ns, name, None)
            if isinstance(member_cls, type) and issubclass(member_cls, BaseModel):
                fields.append(ModelField(
                    name=name, alias=name, py_type=name, kind="json",
                    required=True, model_ref=name,
                ))
                children.append(member_cls)
        return ModelSchema(fields=fields, is_oneof=True), children

    fields = []
    for fname, f in cls.model_fields.items():
        if fname == "additional_properties":
            continue
        tp = f.annotation
        kind = typing.cast(FlagKind, field_kind(tp))
        ref, ref_list, variants = _resolve_ref(tp)
        example = f.examples[0] if getattr(f, "examples", None) else None
        fields.append(ModelField(
            name=fname,
            alias=f.alias or fname,
            py_type=str(tp) if kind == "json" else scalar_type(tp),
            kind=kind,
            required=f.is_required(),
            description=f.description or "",
            enum_values=enum_values(unwrap_optional(tp)),
            default=None if f.is_required() else f.default,
            example=example,
            model_ref=ref,
            model_ref_list=ref_list,
            variant_refs=variants,
        ))
        base = unwrap_optional(tp)
        origin = typing.get_origin(base)
        if origin in (list, set):
            args = typing.get_args(base)
            base = unwrap_optional(args[0]) if args else None
        if isinstance(base, type) and issubclass(base, BaseModel):
            children.append(base)
        for vname in variants or []:
            vcls = getattr(sys.modules[cls.__module__], vname, None)
            if isinstance(vcls, type) and issubclass(vcls, BaseModel):
                children.append(vcls)
    return ModelSchema(fields=fields), children


def registry_from_models(roots: list[type[BaseModel]]) -> dict[str, ModelSchema]:
    """Deduped registry of every model reachable from ``roots``.

    Keyed by ``cls.__name__``; assumes globally-unique model class names (true for
    openapi-generator single-`models`-module output). A future multi-spec product
    with colliding names would need module-qualified keys.
    """
    registry: dict[str, ModelSchema] = {}
    queue = list(roots)
    while queue:
        cls = queue.pop()
        if cls.__name__ in registry:
            continue
        schema, children = _model_to_schema(cls)
        registry[cls.__name__] = schema           # emit once → cycle-safe
        queue.extend(children)
    return registry


def _root_models(package: str, inv: OperationInventory) -> list[type[BaseModel]]:
    """Resolve the body-model classes named in the inventory to live classes."""
    names: set[str] = set()
    for op in inv.operations:
        names.update(op.body_fields.keys())
    models_mod = importlib.import_module(f"{package}.models")
    roots: list[type[BaseModel]] = []
    for name in sorted(names):
        cls = getattr(models_mod, name, None)
        if isinstance(cls, type) and issubclass(cls, BaseModel):
            roots.append(cls)
    return roots


def build_model_registry(
    package: str, sdk_path: Path, inv: OperationInventory
) -> dict[str, ModelSchema]:
    added = str(sdk_path) not in sys.path
    if added:
        sys.path.insert(0, str(sdk_path))
    try:
        return registry_from_models(_root_models(package, inv))
    finally:
        if added and str(sdk_path) in sys.path:
            sys.path.remove(str(sdk_path))
```

> Implementer note: `op.body_fields` keys are the body model names (union variants are individual keys — `introspect.py:256-267`). Resolving them from `{package}.models` mirrors how the runtime resolves `getattr(models, binding.body_model)`. Reviewer-confirmed: `fakesdk` exposes `{package}.models` as a module AND the real `prisma_browser/models/__init__.py` re-exports **every** model class (standard OAG output — e.g. `AccessAndDataPostApplications`), so `getattr(import_module(f"{package}.models"), name)` resolves all roots in both layouts. Nested children are resolved from live annotations (not this module), so they're unaffected regardless. No per-file-module fallback is needed.

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_modelschema.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/modelschema.py tests/test_cli_modelschema.py
git commit -m "feat(cli): build deduped model registry by recursing live SDK body models"
```

---

## Task 5: Extend the `fakesdk` fixture with nested / oneOf / list / cyclic body models

> **Reordered before the wiring task** (Reviewer feedback): the wiring test (Task 6) needs a real `model_ref` target, so the fixture lands first — no `xfail` placeholder.

**Files:**
- Modify: `tests/fixtures/fakesdk/fakesdk/models.py`
- Test: `tests/test_cli_modelschema.py` (add a fixture-driven assertion)

**Why:** the wiring (Task 6) and emitted behavioral tests (Tasks 7–10) need a real complex body field. Today `WidgetInput.spec` is `Optional[dict]` (anonymous → no `model_ref`). Add a nested **all-optional** model (`WidgetProfile`, exercises the non-empty guarantee), a `list[Model]` field, an inline `oneOf` field, and a self-referential cycle.

**Interfaces:**
- Consumes: `registry_from_models`/`build_model_registry` (Task 4), `synth_skeleton` (Task 3).
- Produces: `WidgetInput.profile: Optional[WidgetProfile]`; models `WidgetProfile` (all-optional, with a nested `Contact` + a `list[Tag]` + a `Union[EmailTarget, PhoneTarget]` field) and a `Node` self-cycle. `WidgetInput` stays the body of `create_widget` (already wired in `api.py`), so no new operation is required.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_modelschema.py`:

```python
def test_fakesdk_registry_covers_nested_models() -> None:
    from pathlib import Path

    from phantasos.generator.cli.classify import cli_operations
    from phantasos.generator.cli.modelschema import build_model_registry

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = cli_operations("fakesdk", fixture)
    reg = build_model_registry("fakesdk", fixture, inv)
    assert "WidgetProfile" in reg
    # all-optional → minimal skeleton must be non-empty (first field)
    from phantasos.generator.cli.ir import synth_skeleton
    assert synth_skeleton(reg, "WidgetProfile", full=False) != {}
    # the inline oneOf field becomes variant_refs; the list[Tag] field marks model_ref_list
    prof = reg["WidgetProfile"]
    target = next(f for f in prof.fields if f.name == "target")
    assert target.variant_refs == ["EmailTarget", "PhoneTarget"]
    tags = next(f for f in prof.fields if f.name == "tags")
    assert tags.model_ref == "Tag" and tags.model_ref_list is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_modelschema.py::test_fakesdk_registry_covers_nested_models -v`
Expected: FAIL (`assert 'WidgetProfile' in reg`).

- [ ] **Step 3: Extend `fakesdk/models.py`**

Add (above `WidgetInput`), and add `profile` to `WidgetInput`:

```python
class Tag(BaseModel):
    label: str


class EmailTarget(BaseModel):
    email: str


class PhoneTarget(BaseModel):
    phone: str


class Contact(BaseModel):
    name: str                       # required
    timezone: Optional[str] = None


class Node(BaseModel):              # self-referential cycle
    label: str
    child: Optional["Node"] = None


class WidgetProfile(BaseModel):     # all-optional → exercises non-empty guarantee
    contact: Optional[Contact] = None
    tags: list[Tag] = []
    target: Optional[Union[EmailTarget, PhoneTarget]] = None
    graph: Optional[Node] = None
```

Then add to `WidgetInput` (after `spec`):

```python
    profile: Optional[WidgetProfile] = None  # nested model -> json flag with model_ref
```

Add `Node.model_rebuild()` at module end if needed for the forward ref.

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_modelschema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/fakesdk/fakesdk/models.py tests/test_cli_modelschema.py
git commit -m "test(fixtures): add nested/oneOf/list/cyclic body models to fakesdk for IR-deepening tests"
```

---

## Task 6: Wire the registry into `build_cli_ir` + set `Flag.model_ref` + thread callers

**Files:**
- Modify: `src/phantasos/generator/cli/classify.py:174-200` (`fields_to_flags`), `:244-250` (`_body_flags_for`), `build_cli_ir` signature + assembly
- Modify: `src/phantasos/cli.py:88-92`, `:122-126`
- Modify: `tests/conftest.py:58` (`emit_cli._emit` — feeds ALL Task 10 docs tests), `tests/test_cli_emitted.py` (audit all 5 `build_cli_ir(` sites: 36, 95, 898, 1188, 1468), `tests/test_cli_emitted_real.py` (optional — see note)
- Test: `tests/test_cli_classify.py`

**Interfaces:**
- Consumes: `build_model_registry` (Task 4), `ModelSchema` (Task 2), `WidgetProfile` fixture (Task 5).
- Produces: `build_cli_ir(inv, cfg, *, models: dict[str, ModelSchema] | None = None) -> tuple[CliIR, list[str]]`. When `models` is provided: `CliIR.models = models` and every json body `Flag` gets `model_ref` set (matched by **field name** — `FieldInfo.name` to `ModelField.name`, both python field names, not aliases). When `None`: `CliIR.models = {}`, `model_ref` stays `None` (today's behavior — backward compatible).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_classify.py`:

```python
def test_build_cli_ir_sets_model_ref_and_registry() -> None:
    from pathlib import Path

    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.modelschema import build_model_registry

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = cli_operations("fakesdk", fixture)
    models = build_model_registry("fakesdk", fixture, inv)
    ir, _ = build_cli_ir(inv, CliConfig(), models=models)

    # WidgetInput.profile is the nested model field added in Task 5.
    create = next(c for c in ir.commands if c.key == "create:widget")
    profile = next(f for f in create.body_flags if f.param == "profile")
    assert profile.kind == "json"
    assert profile.model_ref == "WidgetProfile"
    assert "WidgetProfile" in ir.models
```

(No `xfail` — Task 5 already landed `WidgetProfile`. `CliConfig()` is constructed directly, matching every existing `test_cli_classify.py` test — there is no `_cfg()` helper.)

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_classify.py::test_build_cli_ir_sets_model_ref_and_registry -v`
Expected: FAIL (`build_cli_ir() got an unexpected keyword argument 'models'`).

- [ ] **Step 3: Implement the wiring**

In `classify.py`:

```python
def fields_to_flags(
    fields: list[FieldInfo], schema: "ModelSchema | None" = None
) -> list[Flag]:
    refmap = {mf.name: mf for mf in schema.fields} if schema else {}
    flags: list[Flag] = []
    for f in fields:
        if f.kind == "enum":
            py_type = "str"
        elif f.kind == "scalar":
            py_type = f.scalar_type
        else:
            py_type = "str"
        mf = refmap.get(f.name)
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
                model_ref=(mf.model_ref if mf else None),
            )
        )
    return flags
```

Thread the registry into `_body_flags_for`:

```python
def _body_flags_for(
    op: OperationInfo, model: str | None, models: dict[str, "ModelSchema"] | None
) -> list[Flag]:
    reg = models or {}
    if model and model in op.body_fields:
        return fields_to_flags(op.body_fields[model], reg.get(model))
    for name, fields in op.body_fields.items():
        return fields_to_flags(fields, reg.get(name))
    return []
```

Change `build_cli_ir` signature to `def build_cli_ir(inv, cfg, *, models=None)`, pass `models` down to every `_body_flags_for(...)` call, and in the final `CliIR(...)` assembly add `models=models or {}`. Add `from .ir import ModelSchema` to the imports.

In `src/phantasos/cli.py`, both `cli_discover` and `cli_build`:

```python
inv = cli_operations(loaded.config.package, Path(loaded.output_dir))
from .generator.cli.modelschema import build_model_registry
models = build_model_registry(
    loaded.config.package, Path(loaded.output_dir), inv
)
ir, unmapped = build_cli_ir(inv, cfg, models=models)
```

**Thread the registry into every test fixture that emits a CLI consumed by behavioral tests.** The one-liner:

```python
from phantasos.generator.cli.modelschema import build_model_registry
inv = cli_operations("fakesdk", FIXTURE)
ir = build_cli_ir(inv, CONFIG, models=build_model_registry("fakesdk", FIXTURE, inv))[0]
```

Apply at, and only at, these sites (grep `build_cli_ir(` in each file first):
- **`tests/conftest.py:58`** (`emit_cli._emit`) — REQUIRED; every Task 10 docs test depends on it:
  ```python
  inv = cli_operations("fakesdk", fixture)
  from phantasos.generator.cli.modelschema import build_model_registry
  ir = build_cli_ir(inv, config, models=build_model_registry("fakesdk", fixture, inv))[0]
  ```
- **`tests/test_cli_emitted.py`** — the emit fixtures at lines **36** (`emitted`), **95** (`emitted_auth`), **1468** (third emit fixture). REQUIRED.
- **`tests/test_cli_emitted.py:898` and `:1188`** (inline unit `build_cli_ir(inv, …)`): read each test's assertions. If it asserts on body skeletons / `--help` / `model_ref`, pass `models=…`; otherwise leave `models=None` and add `# intentionally exercises the un-deepened (models=None) path`.
- **`tests/test_cli_emitted_real.py`** — updating is **optional**. `models=None` keeps these (skip-guarded, real-SDK) tests green; building the real registry per-test is slow. Only pass `models=` at a site that asserts on registry/`model_ref` behavior; do NOT bulk-edit all ~6 sites.

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_classify.py tests/test_cli_emitted.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/classify.py src/phantasos/cli.py tests/conftest.py tests/test_cli_classify.py tests/test_cli_emitted.py
git commit -m "feat(cli): thread model registry into build_cli_ir and stamp Flag.model_ref"
```

---

## Task 7: `--help` stop-gap — inject `[json: <Model>] e.g. {skeleton}`

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py:166-192` (`_flag_view`) + its callers that pass `models`
- Test: `tests/test_cli_render.py` and `tests/test_cli_emitted.py`

**Interfaces:**
- Consumes: `synth_skeleton` (Task 3), `CliIR.models`, `Flag.model_ref`.
- Produces: a json flag's `help_literal` becomes `"{help} [json: {model_ref}] e.g. {compact-minimal-skeleton}"` (single line; `json.dumps(skeleton, separators=(",", ":"))`). `_flag_view(f, panel=None, *, models=None)`; thread `models` from the render entrypoint through `_command_view` to `_flag_view`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_render.py`:

```python
def test_flag_view_injects_json_annotation_and_skeleton() -> None:
    from phantasos.generator.cli.ir import ModelField, ModelSchema
    from phantasos.generator.cli.ir import Flag
    from phantasos.generator.cli.render_cli import _flag_view

    models = {"WidgetProfile": ModelSchema(fields=[
        ModelField(name="contact", alias="contact", py_type="str", kind="json",
                   required=False, model_ref="Contact"),
    ]), "Contact": ModelSchema(fields=[
        ModelField(name="name", alias="name", py_type="str", kind="scalar", required=True),
    ])}
    f = Flag(name="--profile", param="profile", py_type="str", kind="json",
             required=False, help="Widget profile.", model_ref="WidgetProfile")
    view = _flag_view(f, models=models)
    assert "[json: WidgetProfile]" in view["help_literal"]
    assert '{\\"contact\\":{\\"name\\":\\"string\\"}}' in view["help_literal"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_render.py::test_flag_view_injects_json_annotation_and_skeleton -v`
Expected: FAIL (`_flag_view() got an unexpected keyword argument 'models'`).

- [ ] **Step 3: Implement the injection**

In `render_cli.py`, import `synth_skeleton` from `.ir`, change `_flag_view`:

```python
def _flag_view(
    f: Flag, panel: str | None = None, *, models: dict[str, "ModelSchema"] | None = None
) -> dict[str, object]:
    choices = f.choices
    help_text: str | None = f.help
    completion: list[str] | None = None
    completer_name: str | None = None
    if choices:
        listed = ", ".join(choices)
        values = rf"\[values: {listed}]"
        help_text = f"{f.help}  {values}" if f.help else values
        completion = choices
        completer_name = f"_complete_{_py_name(f.param)}"
    elif f.kind == "json" and f.model_ref and models is not None:
        import json as _json

        skel = synth_skeleton(models, f.model_ref, full=False)
        compact = _json.dumps(skel, separators=(",", ":"))
        ann = rf"\[json: {f.model_ref}] e.g. {compact}"
        help_text = f"{f.help}  {ann}" if f.help else ann
    return {
        # ... unchanged keys ...
    }
```

Thread `models` from the render entrypoint: add a `models=None` kwarg to `_command_view(...)` and pass it into each `_flag_view(...)` call for body flags. There are **two** `_command_view` call sites in `render_cli.py` — line **368** (`by_resource[...].append(_command_view(c, variant_groups))`, feeds `commands.py.jinja` → the emitted `--help`) and line **388** (`all_views = [_command_view(c, variant_groups) for c in ir.commands]`, feeds `app.py.jinja`). Pass `models=ir.models` at **both** so the `--help` annotation is consistent across the command and app surfaces.

- [ ] **Step 4: Run the tests + emitted behavioral check**

Add to `tests/test_cli_emitted.py`:

```python
def test_emitted_help_shows_json_skeleton(emitted: Path) -> None:
    import os, subprocess, sys
    # Force a wide, non-interactive terminal so Rich does NOT wrap the help columns
    # (a wrapped "[json: WidgetProfile]" would split the token and flake the assert).
    env = {**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}
    out = subprocess.run(
        [sys.executable, "-m", "fakesdk_cli", "create", "widget", "--help"],
        capture_output=True, text=True, cwd=str(emitted), env=env,
    )
    text = out.stdout + out.stderr
    # Assert ONLY the two short, wrap-safe tokens here; the exact compact-JSON
    # skeleton string is asserted in the _flag_view unit test (no wrapping there).
    assert "[json:" in text and "WidgetProfile" in text
```

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_render.py tests/test_cli_emitted.py::test_emitted_help_shows_json_skeleton -v`
Expected: PASS. (Rich may wrap the help; assert on short substrings, never the full compact JSON.)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/render_cli.py tests/test_cli_render.py tests/test_cli_emitted.py
git commit -m "feat(cli): --help stop-gap — inject [json: <Model>] + minimal skeleton for json flags"
```

---

## Task 8: One-line docs invocation — real skeleton instead of `'{}'`

**Files:**
- Modify: `src/phantasos/generator/cli/examples.py:25-59` (`example_value`, `render_invocation`)
- Modify: `src/phantasos/generator/cli/docs.py:140` (pass `models` into `render_invocation`)
- Test: `tests/test_cli_docs.py` / `tests/test_sdk_docs_examples.py` analog

**Interfaces:**
- Consumes: `synth_skeleton` (Task 3), `CliIR.models`.
- Produces: `example_value(flag, models=None)` returns `"'{compact-minimal-skeleton}'"` for a json flag with `model_ref` (single-quoted for the shell); falls back to `"'{}'"` for anonymous json (no `model_ref`). `render_invocation(command, *, distribution, override=None, models=None)` threads `models` to `example_value`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_docs.py` (or `tests/test_cli_render.py`):

```python
def test_example_value_renders_minimal_skeleton_for_json() -> None:
    from phantasos.generator.cli.examples import example_value
    from phantasos.generator.cli.ir import Flag, ModelField, ModelSchema

    models = {"P": ModelSchema(fields=[
        ModelField(name="contact", alias="contact", py_type="str", kind="json",
                   required=False, model_ref="C"),
    ]), "C": ModelSchema(fields=[
        ModelField(name="name", alias="name", py_type="str", kind="scalar", required=True),
    ])}
    f = Flag(name="--profile", param="profile", py_type="str", kind="json",
             required=True, model_ref="P")
    assert example_value(f, models) == "'{\"contact\":{\"name\":\"string\"}}'"


def test_example_value_anonymous_json_falls_back() -> None:
    from phantasos.generator.cli.examples import example_value
    from phantasos.generator.cli.ir import Flag

    f = Flag(name="--spec", param="spec", py_type="str", kind="json", required=True)
    assert example_value(f, {}) == "'{}'"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_docs.py::test_example_value_renders_minimal_skeleton_for_json -v`
Expected: FAIL (`example_value() takes 1 positional argument but 2 were given`).

- [ ] **Step 3: Implement**

In `examples.py`:

```python
def example_value(flag: Flag, models: dict[str, "ModelSchema"] | None = None) -> str:
    """A shell-safe example value token for one flag."""
    if flag.choices:
        return flag.choices[0]
    if flag.kind == "json":
        if flag.model_ref and models:
            import json as _json

            from .ir import synth_skeleton

            skel = synth_skeleton(models, flag.model_ref, full=False)
            return "'" + _json.dumps(skel, separators=(",", ":")) + "'"
        return "'{}'"
    if flag.kind == "file":
        return "./file"
    if flag.kind == "id":
        return '"example"'
    return _SCALARS.get(flag.py_type, '"example"')
```

Add `models` param to `render_invocation(...)` and pass it: `parts.append(f"{f.name} {example_value(f, models)}")`. In `docs.py:_command_view`, accept `models` and pass `render_invocation(c, distribution=distribution, override=override, models=models)`; thread `models=ir.models` from `build_cli_docs_context` through the `grouped` comprehension's `_command_view(...)` calls.

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_docs.py tests/test_cli_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/examples.py src/phantasos/generator/cli/docs.py tests/test_cli_docs.py
git commit -m "feat(cli-docs): render real minimal skeleton in one-line invocation example"
```

---

## Task 9: Runtime error example — registry-driven, debug-adaptive

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja:271-337`
- Test: `tests/test_cli_emitted.py`

**Interfaces:**
- Consumes: `synth_skeleton` (in `spec.py` at runtime), `_ir().models`, `Flag.model_ref`, the logging seam `_config.log_level_int(_config.get().logging.level)` (local `from . import config as _config`).
- Produces: when a json flag's value fails to parse, `exc.example` is the registry skeleton — **full** when debug logging is active (`log_level_int(level) <= 10`), else the **minimal non-empty** skeleton. The human-readable `exc.expected` string (array/object + min/max items) stays live-model-derived (unchanged). Anonymous json (no `model_ref`) keeps today's `{"key": "value"}` fallback.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_emitted.py`:

Drive the REAL emitted CLI (house style — every other runtime error test uses
`CliRunner().invoke(main.app, …)`; do NOT reach into `_build_body`). Two cases —
minimal (default) and **full (debug)** — so D10's debug branch is actually tested:

```python
def test_runtime_json_error_example_minimal_and_debug_full(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = _fake_client([])
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    argv = ["create", "widget", "--name", "w", "--priority", "1",
            "--profile", "notjson"]

    # default level → MINIMAL non-empty skeleton: first member (contact) + its
    # required field; the OPTIONAL `tags` is omitted.
    res = CliRunner().invoke(main.app, argv)
    assert res.exit_code != 0
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "contact" in res.stderr        # registry skeleton, not {}
    assert "'{}'" not in res.stderr       # never the broken empty fallback
    assert "tags" not in res.stderr       # optional field absent at minimal

    # debug level → FULL skeleton includes optional fields (e.g. tags). Config is
    # cached at import; set env THEN clear the cache before re-invoking (CLAUDE.md).
    monkeypatch.setenv("FAKESDK_LOGGING_LEVEL", "debug")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    res2 = CliRunner().invoke(main.app, argv)
    assert "tags" in res2.stderr          # optional field => full skeleton only


def test_runtime_anonymous_json_error_keeps_keyvalue_example(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D11: a json flag with NO model_ref (--spec: Optional[dict]) keeps the live
    # `{"key": "value"}` fallback — it must NOT regress to an empty/missing example.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = _fake_client([])
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--spec", "notjson"],
    )
    assert res.exit_code != 0
    assert "key" in res.stderr and "value" in res.stderr
```

> `_fake_client` and the `main`/`facade` import pattern mirror the existing
> `test_invalid_json_flag_reports_clean_error` (`tests/test_cli_emitted.py:648`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_emitted.py::test_runtime_json_error_example_minimal_and_debug_full -v`
Expected: FAIL (today's `_skeleton` returns `{}` for all-optional `WidgetProfile`; `"contact"` absent). The anonymous-json test passes today and must STILL pass after Step 3 (guards the D11 fallback).

- [ ] **Step 3: Implement the runtime change**

In `runtime.py.jinja`, extend the EXISTING `.spec` import (line 29) — `json` is already imported (line 11), and `config` is imported **locally** as `_config` inside functions (lines 67/84/428), so do NOT add a module-level config import:

```python
from .spec import CliIR, Command, Flag, MethodBinding, synth_skeleton  # add synth_skeleton
```

Replace the example computation. Keep `_describe_json_field` producing the `expected` string from the live model, but compute the `example` from the registry. In `_build_body`, change the `except InputError` block:

```python
        except InputError as exc:
            fl = flags[k]
            if fl.kind == "json" and exc.expected is None:
                exp, live_ex = _describe_json_field(model_cls, k)
                exc.expected = exp
                reg = _registry_example(fl)
                # D11: registry skeleton for known models; anonymous json (no
                # model_ref → reg is None) keeps the live {"key": "value"} fallback.
                ex = reg if reg is not None else live_ex
                exc.example = f"{fl.name} '{ex}'" if ex else None
            raise
```

Add the registry example helper (anywhere in the module):

```python
def _registry_example(flag: Flag) -> str | None:
    if not flag.model_ref:
        return None
    from . import config as _config  # local import — the module's convention
    full = _config.log_level_int(_config.get().logging.level) <= 10  # debug or trace
    skel = synth_skeleton(_ir().models, flag.model_ref, full=full)
    return json.dumps(skel, separators=(",", ":"))
```

(`_ir()` is the existing cached IR loader, `runtime.py.jinja:32`.) Leave `_skeleton`/`_placeholder` in place for the `expected`-string path (`_describe_json_field` still uses `_skeleton(inner)` only to decide array-of-objects vs array — that text is fine; only the example value moves to the registry).

> `log_level_int` + `get().logging.level` exist in `_generated.config` (`config.py.jinja:279`, `:53-79`). If `logging.file` is unset the level still resolves; no file is required.

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/test_cli_emitted.py -v`
Expected: PASS (new test + existing runtime tests like `test_runtime_friendly_error_on_sdk_exception`).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-runtime): debug-adaptive registry-driven JSON skeleton in input errors"
```

---

## Task 10: Docs progressive-disclosure rendering (details + tabs + full skeleton)

**Files:**
- Modify: `src/phantasos/generator/cli/docs.py:115-142` (`_flag_row`, `_command_view`)
- Modify: `src/phantasos/generator/cli/templates/docs/reference_object.md.jinja`
- Modify: `src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja:34-39`
- Test: `tests/cli/test_docs_emitted.py`, `tests/test_cli_docs.py`

**Interfaces:**
- Consumes: `CliIR.models`, `Flag.model_ref`, `synth_skeleton` (Task 3).
- Produces: each json `_flag_row` gains `schema: <rendered nested rows>` (recursive, cycle-broken) and the command view gains `body_skeleton: <full skeleton JSON string>`. The reference template renders, per json flag, a **collapsed** `??? note "<flag> schema"` block with the nested field table (sub-models as nested collapsibles; inline `oneOf` as `=== "Variant"` tabs), and per command a collapsed `??? example "Full body (copy & fill)"` fenced JSON block. `mkdocs.yml` gains `pymdownx.details`, `attr_list`, `pymdownx.tabbed` (`alternate_style: true`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/cli/test_docs_emitted.py`:

```python
def test_reference_page_renders_nested_schema_disclosure(emit_cli) -> None:
    # emit_cli + CliDocsConfig are the existing conftest fixture + import (already in
    # tests/cli/test_docs_emitted.py); _emit:58 must thread models= (Task 6).
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    assert '??? note "`--profile` schema"' in text   # collapsed details block
    assert "Full body" in text                        # copy & fill skeleton block
    # The nested table MUST be indented (4 spaces) so it stays INSIDE the ??? block.
    # Catches the indent(first=True) bug structurally — runs even when mkdocs is absent.
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("??? note"))
    body = next(ln for ln in lines[i + 1:] if ln.strip())  # first non-blank after header
    assert body.startswith("    "), f"schema body escaped the ??? block: {body!r}"


def test_mkdocs_enables_details_and_tabbed(emit_cli) -> None:
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    exts = cfg["markdown_extensions"]
    flat = [e if isinstance(e, str) else list(e)[0] for e in exts]
    assert "pymdownx.details" in flat
    assert "attr_list" in flat
    assert any("tabbed" in (e if isinstance(e, str) else list(e)[0]) for e in exts)
```

> `emit_cli` lives in `tests/conftest.py:19` and its `_emit(*, docs: CliDocsConfig | None = None, auth=False)` builds the IR at line 58 — Task 6 threads `models=` there. `CliDocsConfig` and `yaml` are already imported in `tests/cli/test_docs_emitted.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_reference_page_renders_nested_schema_disclosure tests/cli/test_docs_emitted.py::test_mkdocs_enables_details_and_tabbed -v`
Expected: FAIL.

- [ ] **Step 3a: Build the nested schema view in `docs.py`**

```python
def _schema_rows(models, name, *, _path=()):
    """Recursive rows for a model: [{name, type, required, help, choices, children, tabs}]."""
    schema = models.get(name)
    if schema is None or name in _path:
        return []
    path = (*_path, name)  # tuple unpack (ruff RUF005), not _path + (x,)
    rows = []
    for mf in schema.fields:
        tabs = None
        children = None
        if mf.variant_refs:
            tabs = [{"name": v, "rows": _schema_rows(models, v, _path=path)}
                    for v in mf.variant_refs]
        elif mf.model_ref:
            children = _schema_rows(models, mf.model_ref, _path=path)
        rows.append({
            "name": mf.alias,
            "type": (f"list[{mf.model_ref}]" if mf.model_ref_list else
                     mf.model_ref or mf.py_type),
            "required": mf.required,
            "help": _cell(mf.description),
            "choices": [_cell(c) for c in mf.enum_values] if mf.enum_values else None,
            "children": children,
            "tabs": tabs,
        })
    return rows


def _flag_row(f: Flag, models=None) -> dict[str, object]:
    schema = None
    if f.kind == "json" and f.model_ref and models:
        schema = _schema_rows(models, f.model_ref)
    return {
        "name": f.name,
        "type": (f.model_ref or f.py_type),
        "required": f.required,
        "choices": [_cell(c) for c in f.choices] if f.choices else None,
        "help": _cell(f.help),
        "schema": schema,
    }
```

In `_command_view`, accept `models`, build body rows with it, and add the full skeleton: collect the body flags' `model_ref`s into one object keyed by flag alias:

```python
    body_skeleton = {
        f.param: synth_skeleton(models, f.model_ref, full=True)
        for f in body if f.kind == "json" and f.model_ref
    } if models else {}
    ...
    "body_flags": [_flag_row(f, models) for f in body],
    "body_skeleton": json.dumps(body_skeleton, indent=2) if body_skeleton else "",
```

Thread `models=ir.models` from `build_cli_docs_context` into the `_command_view(...)` calls (same comprehension touched in Task 8).

- [ ] **Step 3b: Render in `reference_object.md.jinja`**

Extend the `flag_table` macro so a json row with `f.schema` emits a collapsed details block after the row, and add a recursive macro for nested rows + tabs. Replace the macro region:

```jinja
{% macro schema_block(rows) -%}
| Field | Type | Required | Description |
| --- | --- | --- | --- |
{% for r in rows -%}
| `{{ r.name }}` | `{{ r.type }}` | {{ "yes" if r.required else "no" }} | {{ r.help }}{% if r.choices %} _(values: {{ r.choices | join(", ") }})_{% endif %} |
{% endfor %}
{% for r in rows %}{% if r.tabs %}
{% for t in r.tabs %}
=== "{{ t.name }}"

{{ schema_block(t.rows) | indent(4, first=True) }}
{% endfor %}
{% elif r.children %}
??? note "`{{ r.name }}` fields"

{{ schema_block(r.children) | indent(4, first=True) }}
{% endif %}{% endfor %}
{%- endmacro -%}

{% macro flag_table(rows) -%}
| Flag | Type | Required | Description |
| --- | --- | --- | --- |
{% for f in rows -%}
| `{{ f.name }}` | `{{ f.type }}` | {{ "yes" if f.required else "no" }} | {{ f.help }}{% if f.choices %} _(values: {{ f.choices | join(", ") }})_{% endif %} |
{% endfor %}
{% for f in rows %}{% if f.schema %}
??? note "`{{ f.name }}` schema"

{{ schema_block(f.schema) | indent(4, first=True) }}
{% endif %}{% endfor %}
{%- endmacro -%}
```

> **Indentation is load-bearing — use `indent(4, first=True)`, NOT bare `indent(4)`.** Jinja's `indent(width)` defaults to `first=False`, so the FIRST line of the nested table is left at column 0 — which terminates the enclosing `pymdownx.details`/`tabbed` block, spilling the table outside the collapsible and failing `mkdocs build --strict`. `first=True` indents every line (matching the `body_skeleton` block below). Jinja2 macros **can** self-recurse (the macro name is bound in its own scope), and the `indent` filter chain compounds across depth (a depth-2 table ends up at 8 spaces), which is exactly what nested `???` levels need. The unused `depth` counter is dropped — indentation comes entirely from the filter chain.

After the Body `flag_table(cmd.body_flags)` block, add the full skeleton:

```jinja
{% if cmd.body_skeleton %}
??? example "Full body (copy & fill)"

    ```json
{{ cmd.body_skeleton | indent(4, first=True) }}
    ```

{% endif %}
```

- [ ] **Step 3c: Enable the extensions in `mkdocs.yml.jinja`**

Replace `markdown_extensions:` with:

```jinja
markdown_extensions:
  - admonition
  - attr_list
  - pymdownx.details
  - pymdownx.highlight
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - toc:
      permalink: true
```

- [ ] **Step 4: Run the tests + real mkdocs strict build**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py tests/test_cli_docs.py -v`
Expected: PASS.

**The `mkdocs build --strict` gate (D12).** There is NO existing in-suite strict build (`tests/test_sdk_docs_emitted.py` only asserts on emitted text), and mkdocs-material may not be in the offline-gate venv. So the strict build is guaranteed at TWO levels, neither of which can silently pass:
1. **In-suite (always runs):** the structural-indent assertion above — it fails loudly if the `???`/`tabbed` indentation regresses, with no mkdocs dependency.
2. **Best-effort in-suite + REQUIRED at the product level:** add a guarded test, but make Task 11's real-product `uv run mkdocs build --strict` a **required, evidence-pasted** gate (it is — Task 11 Step 1/2/4). If mkdocs-material is a docs/test dependency group, prefer running it here too:

```python
def test_emitted_docs_build_strict(emit_cli) -> None:
    import shutil, subprocess
    if shutil.which("mkdocs") is None:
        import pytest
        pytest.skip("mkdocs not installed; strict build is enforced in Task 11")
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    res = subprocess.run(["mkdocs", "build", "--strict"], cwd=str(out),
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
```

If the repo already ships mkdocs-material in a dev/docs dependency group (check `pyproject.toml` — the SDK docs use it), add it to the `gate`/`tests` nox session deps so this test RUNS rather than SKIPs; otherwise the Task 11 product build is the binding gate.

Run it: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_emitted_docs_build_strict -v`
Expected: PASS (or SKIP, with Task 11 as the binding strict gate).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/docs.py src/phantasos/generator/cli/templates/docs/reference_object.md.jinja src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja tests/cli/test_docs_emitted.py tests/test_cli_docs.py
git commit -m "feat(cli-docs): progressive-disclosure nested schema (details + oneOf tabs + full skeleton)"
```

---

## Task 11: End-to-end verification on real products + docs/changelog

**Files:**
- Verify (no edit): `products/prisma-browser/`, `products/posture/`
- Modify: `.agents/context/` CLI-generator deep-dive, `CHANGELOG.md`

**Interfaces:** none (integration + docs).

- [ ] **Step 1: Build the real prisma-browser CLI + docs and inspect**

Run (adjust the build entrypoint to the repo's actual command — check `src/phantasos/cli.py` / nox):

```bash
export UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos NOX_ENVDIR=$HOME/.tmp/phantasos-nox
uv run python -m phantasos cli-build --product prisma-browser   # or the real CLI-build entry
```

Expected evidence to capture and paste:
- `_generated/ir.json` contains a non-empty `"models"` map and the `--applications` flag carries `"model_ref": "AccessAndDataPostApplications"`.
- `… create access-and-data-rule --help` shows `[json: AccessAndDataPostApplications] e.g. {"saas":{"accessMode":"none"}}`.
- `docs/reference/access-and-data-rule.md` has collapsed `???` schema blocks + a "Full body (copy & fill)" skeleton, with the nested tables indented 4 spaces (inside the block).
- **BINDING D12 GATE — required:** `uv run mkdocs build --strict` (in the emitted prisma-browser docs dir) **exits 0**. This is the authoritative strict-build check (the in-suite test may SKIP if mkdocs-material is absent); do not declare Task 11 done without pasting a `0`-exit build.

- [ ] **Step 2: Repeat the lighter smoke for posture**

```bash
uv run python -m phantasos cli-build --product posture
```
Confirm `posture-check` reference page renders schema disclosure and `mkdocs build --strict` passes.

- [ ] **Step 3: Run the full offline gate + live**

```bash
export UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos NOX_ENVDIR=$HOME/.tmp/phantasos-nox
uv run nox -s gate
uv run nox -s live    # skips without credentials
```
Expected: gate green (0 failed); live passes or skips.

- [ ] **Step 4: Update context deep-dive + CHANGELOG**

Update the CLI-generator `.agents/context/` deep-dive narrative (the new `modelschema.py` seam, `CliIR.models`, `Flag.model_ref`, the `ir.py` synthesizer shipped to `spec.py`, the docs disclosure, the debug-adaptive error example), then:

```bash
uv run nox -s context        # refresh generated blocks
uv run nox -s context -- --check
```

Add under `## [Unreleased]` in `CHANGELOG.md`:

```markdown
### Added
- Generated CLIs now carry a deduped nested-schema model registry in the IR,
  powering: progressive-disclosure docs (collapsible per-flag schema, oneOf
  tabs, copy-&-fill full-body skeleton), a `[json: <Model>]` `--help` annotation
  with a real minimal skeleton, a real skeleton in the one-line docs invocation,
  and a debug-adaptive JSON skeleton in input-error messages.
```

- [ ] **Step 5: Commit**

```bash
git add .agents/context CHANGELOG.md
git commit -m "docs(cli): document model-registry IR deepening + progressive-disclosure docs"
```

---

## Self-Review (run after drafting; fix inline)

**Spec coverage (D1–D13):**
- D1 scope (IR + docs + `--help` stop-gap incl. real skeleton): Tasks 2–10. ✓
- D2 deduped registry on `CliIR`: Task 2 (model), Task 4 (build). ✓
- D3 schema source = pydantic `model_fields` recursion reusing primitives: Task 1 (promote), Task 4 (recurse). ✓
- D4 two skeleton variants (full docs / minimal `--help`): Task 3 (`full` flag). ✓
- D5 bounding + oneOf (emit once, cycle-break, variant tabs): Task 3 (cycle-break), Task 4 (dedup), Task 10 (tabs). ✓
- D6 docs inline collapsed details + tabs + full skeleton + mkdocs extensions: Task 10. ✓
- D7 CLI-owned `ModelField`/`ModelSchema` (+ `model_ref_list` marker): Task 2. ✓
- D8 recursion in CLI layer reusing public primitives, `FieldInfo` untouched: Task 1 + Task 4. ✓
- D9 minimal non-empty guarantee: Task 3 (`test_minimal_non_empty_guarantee` + the two value-precedence tests), Task 5 (`WidgetProfile` fixture). ✓
- D10 three surfaces + debug-adaptive runtime: Task 7 (`--help`), Task 8 (invocation), Task 9 (runtime — minimal AND debug=full both behaviorally tested). ✓
- D11 synthesizer in `ir.py` shipped via `spec.py`: Task 3 + Task 9 (`from .spec import … synth_skeleton`). ✓
- D12 emitted-behavioral + synthetic-fixture units + strict build: Tasks 3/4 (synthetic), Tasks 7/9/10 (emitted), Task 10 in-suite structural-indent + Task 11 binding `mkdocs build --strict`. ✓
- D13 scope (universal + docs-gated prisma-browser/posture, adem out): Tasks 7–9 universal, Task 10 docs-gated, Task 11 verifies both. ✓

**Placeholder scan:** no "TBD"/"handle edge cases"; every code step shows code. ✓
**Type consistency:** `synth_skeleton(models, name, *, full)` used identically in Tasks 3/7/8/9/10 (`prefer_variant` dropped); `model_ref`/`model_ref_list`/`variant_refs` consistent across Tasks 2/4/10; `build_model_registry(package, sdk_path, inv)` consistent in Tasks 4/5/6. ✓
**Task order:** Task 5 (fixture) precedes Task 6 (wiring) so the wiring test has a real `model_ref` target — no `xfail`. ✓

**Review resolutions (2× python-pro):** Both blockers fixed — Jinja `indent(4, **first=True**)` (else nested tables escape the `???` block / fail `--strict`); `tests/conftest.py:58` `emit_cli` now threads `models=` (else Task 10 renders an empty registry). D11 anonymous-json `{"key":"value"}` fallback restored in Task 9. Both `_command_view` sites (368/388) threaded. Debug=full branch now tested. Task 1 load-bearing aliases documented. `build_cli_ir` call-site audit expanded to all 5 + conftest. `prefer_variant` dropped (YAGNI; oneOf bodies are pre-split). `_resolve_ref` uses `from types import UnionType`. Value-precedence tests added.

**Residual risk:** Rich `--help` wrapping — Task 7 forces `COLUMNS=200`/`TERM=dumb` and asserts only short tokens; the exact compact-JSON is asserted in the no-wrap unit test. `build_cli_ir(models=None)` stays backward-compatible for any un-audited caller.
