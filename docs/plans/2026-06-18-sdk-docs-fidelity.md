# SDK Generated-Docs Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generated SDK docs render each pydantic data model's full field surface and replace opaque `Model(...)` CRUD placeholders with real-shaped, schema-derived examples (with an optional per-product manual override).

**Architecture:** Two independent improvements to the SDK docs stage. (A) Wire the `griffe-pydantic` griffe extension + `show_if_no_docstring` + aggressive member filters into the scaffold's `mkdocs.yml`/`pyproject.toml`, and teach `gen_ref_pages.py` to render oneOf-wrapper pages as links to their variant models. (B) Add a type-driven, cycle-guarded example synthesizer that walks live pydantic model classes to emit real-shaped constructor examples, wired into the docs context with an optional `docs.examples.<slot>` verbatim override and a configurable `docs.showcase_variant`.

**Tech Stack:** Python 3.11+, pydantic v2, Jinja2 scaffold templates, mkdocs-material + mkdocstrings[python] + mkdocs-gen-files + griffe-pydantic, nox, pytest.

## Global Constraints

- Branch: continue on `feature/sdk-generated-docs` (21 ahead of `develop`, no open PR). Do **not** bump `version`. Record user-facing changes under `## [Unreleased]` in `CHANGELOG.md`.
- The generated SDK is a **pure build artifact** — every change lives in `src/phantasos/scaffold/` (shared templates), `src/phantasos/generator/sdk/` (build logic), `src/phantasos/productconfig.py` (config model), or `products/<name>/` (per-product). Never hand-edit files under the generated SDK output dir.
- Test policy (enforced by hooks): prefer **real dependencies**; never mock the system under test. Real pydantic models in synthesizer tests — not mocks. Evidence before assertions: run the command and show real output before claiming a pass.
- Frozen oracles: never edit a `protected_globs` path to make work pass.
- Example **values are honest placeholders**: enums use a real first value; `str→"example"`, `int→0`, `float→0.0`, `bool→False`, `datetime→"2026-01-01T00:00:00Z"`. No name/format guessing (it can produce values invalid for this API).
- Recursion uses a **cycle guard only** (no hard depth/node caps).
- mkdocstrings config values must mirror exactly: extension `griffe_pydantic`; `show_if_no_docstring: true`.
- Run `UV_PROJECT_ENVIRONMENT=/tmp/<name> uv run ...` per the repo's sshfs note when invoking uv/nox.
- Phase boundary: `uv run nox -s gate` (offline; auto-runs on stop) and the `sdk-docs` integration gate must stay green; run `uv run nox -s live` before declaring the work complete.

---

## File Structure

**Create:**
- `src/phantasos/generator/sdk/examples.py` — pure, type-driven example synthesizer over live pydantic classes. No I/O, no template knowledge.
- `tests/test_sdk_docs_examples.py` — unit tests for the synthesizer using real pydantic fixture models.

**Modify:**
- `src/phantasos/scaffold/pyproject.toml.jinja` — add `griffe-pydantic` to the `docs` dependency group.
- `src/phantasos/scaffold/mkdocs.yml.jinja` — `extensions: [griffe_pydantic]`, `show_if_no_docstring: true`, extended `filters`.
- `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` — oneOf-wrapper detection + variant-link rendering.
- `src/phantasos/productconfig.py` — `DocsExamples` model; `examples` + `showcase_variant` on `DocsConfig`.
- `src/phantasos/generator/sdk/docs.py` — resolve body model classes, attach `body_code` (synthesized) per body arg and `example_override` per slot.
- `src/phantasos/scaffold/docs/guides/crud.md.jinja` — consume `body_code` + per-slot `example_override`.
- `src/phantasos/scaffold/docs/getting-started.md.jinja` — read-fallback consumes `body_code`.
- `tests/test_sdk_docs_emitted.py` — adapt fixtures/asserts to `body_code`/`example_override`.
- `tests/test_productconfig.py` — parse `docs.examples` + `docs.showcase_variant`.
- `products/prisma-browser/sdk.yml` — curated `docs.examples.create` (dogfood).
- `noxfile.py` (`sdk-docs` session) — positive assertions: a field description renders; a oneOf wrapper page links its variants; the curated example appears.
- `.agents/context/sdk-generator.md`, `.agents/context/scaffold.md` — docs-stage narrative; refresh generated blocks via `nox -s context`.
- `CHANGELOG.md` — `## [Unreleased]` entries.

---

### Task 1: griffe-pydantic dependency + mkdocstrings configuration

Wires Part A's static config: the extension that surfaces `Field(description=…)` as attribute docs, the option that shows fields lacking descriptions, and the filters that strip openapi-generator boilerplate so pages show only real schema fields.

**Files:**
- Modify: `src/phantasos/scaffold/pyproject.toml.jinja:35-42` (docs group)
- Modify: `src/phantasos/scaffold/mkdocs.yml.jinja:40-65` (plugins.mkdocstrings.handlers.python.options)
- Test: `tests/test_sdk_docs_emitted.py`

**Interfaces:**
- Consumes: existing scaffold context keys (`has_docs`, `package`, …).
- Produces: a generated `mkdocs.yml` whose python handler options contain `show_if_no_docstring: true`, `extensions: [griffe_pydantic]`, and the extended `filters` list; a generated `pyproject.toml` whose `docs` group includes `griffe-pydantic`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sdk_docs_emitted.py`:

```python
def test_mkdocs_enables_griffe_pydantic_and_filters(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    mk = (tmp_path / "mkdocs.yml").read_text()
    assert "griffe_pydantic" in mk
    assert "show_if_no_docstring: true" in mk
    # boilerplate the aggressive filter must hide. NB: mkdocstrings filters are
    # re.search patterns, so the unanchored-tail "!^oneof_schema_" matches every
    # oneof_schema_<n>_validator member — and avoids a backslash that would not
    # survive the verbatim YAML round-trip.
    for pat in ("!^to_dict$", "!^model_config$", "!^additional_properties$",
                "!^actual_instance$", "!^oneof_schema_"):
        assert pat in mk, pat
    pp = (tmp_path / "pyproject.toml").read_text()
    assert "griffe-pydantic" in pp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py::test_mkdocs_enables_griffe_pydantic_and_filters -v`
Expected: FAIL (`assert "griffe_pydantic" in mk`).

- [ ] **Step 3: Add the dependency**

In `src/phantasos/scaffold/pyproject.toml.jinja`, extend the docs group (lines 36-41):

```jinja
docs = [
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.26",
    "mkdocs-gen-files>=0.5",
    "mkdocs-literate-nav>=0.6",
    "griffe-pydantic>=1.0.0",
]
```

- [ ] **Step 4: Add the mkdocstrings options**

In `src/phantasos/scaffold/mkdocs.yml.jinja`, replace the `options:` block (lines 53-64) with:

```yaml
          options:
            docstring_style: sphinx
            extensions:
              - griffe_pydantic
            show_if_no_docstring: true
            filters:
              - "!^_"
              - "!_with_http_info$"
              - "!_without_preload_content$"
              - "!_serialize$"
              - "!^to_str$"
              - "!^to_json$"
              - "!^to_dict$"
              - "!^from_json$"
              - "!^from_dict$"
              - "!^model_config$"
              - "!^additional_properties$"
              - "!^actual_instance$"
              - "!^one_of_schemas$"
              - "!^oneof_schema_"
              - "!^discriminator_value_class_map$"
            show_bases: false
            show_source: false
            show_root_heading: true
            show_docstring_parameters: false
            members_order: source
```

- [ ] **Step 5: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py::test_mkdocs_enables_griffe_pydantic_and_filters -v`
Expected: PASS.

- [ ] **Step 6: Verify the generated mkdocs.yml is valid YAML**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py::test_mkdocs_yaml_safe_with_colon_in_text -v`
Expected: PASS (the `\d+` regex string must not break YAML parsing).

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/scaffold/pyproject.toml.jinja src/phantasos/scaffold/mkdocs.yml.jinja tests/test_sdk_docs_emitted.py
git commit -m "feat(sdk): enable griffe-pydantic + field-level model docs in generated mkdocs"
```

---

### Task 2: oneOf wrapper reference pages render variant links

Teaches the generated `gen_ref_pages.py` to detect openapi-generator oneOf wrappers (e.g. `CreateOrReplaceAppInput`) and emit, on the wrapper's page, a `:::`-anchor for the wrapper class (so type cross-refs resolve under `--strict`) plus a markdown list linking each variant model's own reference page. Links (not duplicate `:::` blocks) avoid duplicate-anchor warnings that would fail `--strict`.

**Files:**
- Modify: `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja:17-34`
- Test: `tests/test_sdk_docs_emitted.py` (emitted-script string asserts); end-to-end coverage in Task 6's gate.

**Interfaces:**
- Consumes: `package` context key.
- Produces: emitted `docs/scripts/gen_ref_pages.py` that, for a module whose public model class has an `actual_instance` field, writes a wrapper page with variant links derived from `cls.model_fields["actual_instance"]`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sdk_docs_emitted.py`:

```python
def test_gen_ref_pages_handles_oneof_wrappers(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    script = (tmp_path / "docs/scripts/gen_ref_pages.py").read_text()
    # detection + variant-link rendering must be present in the emitted script
    assert "actual_instance" in script
    assert "One of the following variants" in script
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py::test_gen_ref_pages_handles_oneof_wrappers -v`
Expected: FAIL.

- [ ] **Step 3: Implement oneOf handling in the gen-files script template**

Replace the body of `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` (between the `{% if has_docs … %}` guard and `{% endif %}`) with:

```jinja
{% if has_docs | default(false) %}"""Generate the API Reference: one mkdocstrings page per api/ and models/ module."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import UnionType
from typing import Union, get_args, get_origin

import mkdocs_gen_files
from pydantic import BaseModel

PACKAGE = "{{ package }}"
SUBPACKAGES = ("api", "models")

# This script lives at <sdk-root>/docs/scripts/gen_ref_pages.py, so parents[2]
# is the SDK root (scripts -> docs -> root) where the package directory lives.
src = Path(__file__).resolve().parents[2] / PACKAGE
assert src.is_dir(), src  # fail loudly if the package path drifts


def _public_model(module_name: str) -> type[BaseModel] | None:
    """The pydantic model a models/ module defines, matched by file<->class name."""
    mod = importlib.import_module(module_name)
    want = module_name.rsplit(".", 1)[-1].replace("_", "").lower()
    for name in dir(mod):
        obj = getattr(mod, name)
        if (isinstance(obj, type) and issubclass(obj, BaseModel)
                and obj.__module__ == module_name and name.replace("_", "").lower() == want):
            return obj
    return None


def _oneof_variants(model: type[BaseModel]) -> list[type[BaseModel]]:
    """Variant classes of an openapi-generator oneOf wrapper (else [])."""
    field = model.model_fields.get("actual_instance")
    if field is None:
        return []
    inner = field.annotation
    if get_origin(inner) in (Union, UnionType):
        return [a for a in get_args(inner)
                if isinstance(a, type) and issubclass(a, BaseModel) and a is not type(None)]
    return []


nav = mkdocs_gen_files.Nav()
for sub in SUBPACKAGES:
    for path in sorted((src / sub).rglob("*.py")):
        module = path.relative_to(src).with_suffix("")
        parts = tuple(module.parts)
        if parts[-1] == "__init__" or parts[-1].startswith("_"):
            continue
        doc_path = Path(*parts).with_suffix(".md")
        full = Path("reference", doc_path)
        nav[parts] = doc_path.as_posix()
        dotted = ".".join((PACKAGE, *parts))
        variants: list[type[BaseModel]] = []
        if sub == "models":
            model = _public_model(dotted)
            if model is not None:
                variants = _oneof_variants(model)
        with mkdocs_gen_files.open(full, "w") as fd:
            fd.write(f"::: {dotted}\n")
            if variants:
                fd.write("\nOne of the following variants:\n\n")
                # Variant pages are siblings of the wrapper page (both under
                # models/), so a bare "<module>.md" relative link resolves.
                for v in variants:
                    fd.write(f"- [{v.__name__}]({v.__module__.rsplit('.', 1)[-1]}.md)\n")
        mkdocs_gen_files.set_edit_path(full, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as fd:
    fd.writelines(nav.build_literate_nav())
{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py::test_gen_ref_pages_handles_oneof_wrappers -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja tests/test_sdk_docs_emitted.py
git commit -m "feat(sdk): render oneOf wrapper reference pages as variant links"
```

---

### Task 3: The example synthesizer

Pure, type-driven, cycle-guarded synthesizer that turns a body model class into a real-shaped constructor expression string. Operates only on live pydantic classes — no template or filesystem knowledge — so it is fully unit-testable with real fixture models.

**Files:**
- Create: `src/phantasos/generator/sdk/examples.py`
- Test: `tests/test_sdk_docs_examples.py`

**Interfaces:**
- Produces: `synthesize_body(model: type[BaseModel], *, variant: str | None = None) -> str` — a multi-line (or single-line for trivial models) Python expression whose opening token starts at column 0. Required fields only, at every level. Picks the named `variant` for a top-level oneOf wrapper (first variant otherwise, and for any nested wrapper). Returns `f"{model.__name__}(...)"` when a cycle is detected.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sdk_docs_examples.py`:

```python
from __future__ import annotations

import datetime
import enum
from typing import Optional, Union

from pydantic import BaseModel, Field, StrictBool, StrictStr

from phantasos.generator.sdk.examples import synthesize_body


# A real str-enum (mirrors the generated SDK's LenientStrEnum, which is a
# `str, Enum`). Not a mock — exercises the synthesizer's real enum path.
class Color(str, enum.Enum):
    RED = "red"
    BLUE = "blue"


class UrlInput(BaseModel):
    url: StrictStr = Field(description="URL pattern")
    strict_mode: Optional[StrictBool] = Field(default=False)  # optional -> omitted


class CustomApp(BaseModel):
    name: StrictStr = Field(description="Name")
    color: Color
    urls: list[UrlInput]
    created_at: datetime.datetime
    note: Optional[str] = None  # optional -> omitted


def test_required_only_with_typed_placeholders() -> None:
    out = synthesize_body(CustomApp)
    assert out == (
        "CustomApp(\n"
        '    name="example",\n'
        '    color="red",\n'
        "    urls=[\n"
        "        UrlInput(\n"
        '            url="example",\n'
        "        ),\n"
        "    ],\n"
        '    created_at="2026-01-01T00:00:00Z",\n'
        ")"
    )
    assert "note" not in out and "strict_mode" not in out


class _Wrapper(BaseModel):
    actual_instance: Optional[Union[CustomApp, UrlInput]] = None


def test_oneof_picks_named_variant() -> None:
    assert synthesize_body(_Wrapper, variant="UrlInput").startswith("UrlInput(")


def test_oneof_defaults_to_first_variant() -> None:
    assert synthesize_body(_Wrapper).startswith("CustomApp(")


def test_cycle_guard_terminates() -> None:
    # required self-reference would recurse forever without the guard
    class A(BaseModel):
        nxt: "A"  # required cycle
    A.model_rebuild()
    out = synthesize_body(A)
    assert out == "A(\n    nxt=A(...),\n)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_examples.py -v`
Expected: FAIL (`ModuleNotFoundError: phantasos.generator.sdk.examples`).

- [ ] **Step 3: Implement the synthesizer**

Create `src/phantasos/generator/sdk/examples.py`:

```python
"""Synthesize illustrative constructor examples from live pydantic models.

Turns an opaque ``Model(...)`` placeholder in the generated CRUD guide into a
real-shaped, type-driven example. Values are honest placeholders: enums use a
real first value; ``str -> "example"``, ``int -> 0``, ``float -> 0.0``,
``bool -> False``, ``datetime -> "2026-01-01T00:00:00Z"``. Domain-perfect
values come from the optional per-product ``docs.examples`` override.
"""

from __future__ import annotations

import datetime
import enum
from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from ..cli.introspect import _enum_values, _unwrap_optional

_INDENT = "    "
_SCALARS = {
    bool: "False",
    int: "0",
    float: "0.0",
    str: '"example"',
}


def _is_wrapper(model: type[BaseModel]) -> bool:
    return "actual_instance" in getattr(model, "model_fields", {})


def _variants(model: type[BaseModel]) -> list[type[BaseModel]]:
    inner = _unwrap_optional(model.model_fields["actual_instance"].annotation)
    args = get_args(inner) if get_origin(inner) in (Union, UnionType) else ()
    # issubclass(a, BaseModel) already excludes NoneType — an explicit
    # `a is not type(None)` here is redundant and trips mypy's
    # comparison-overlap check under `strict = true`.
    return [a for a in args if isinstance(a, type) and issubclass(a, BaseModel)]


def _pick_variant(
    model: type[BaseModel], variant: str | None
) -> type[BaseModel] | None:
    vs = _variants(model)
    if variant:
        for v in vs:
            if v.__name__ == variant:
                return v
    return vs[0] if vs else None


def _continuation_indent(expr: str, pad: str) -> str:
    """Indent every line of ``expr`` except the first by ``pad``.

    The first line follows ``name=`` and must stay flush; deeper lines align
    under their opening token.
    """
    head, _, tail = expr.partition("\n")
    if not tail:
        return head
    indented = "\n".join(pad + line for line in tail.split("\n"))
    return f"{head}\n{indented}"


def _enum_literal(base: type) -> str:
    values = _enum_values(base) or [""]
    first = values[0]
    is_enum = isinstance(base, type) and issubclass(base, enum.Enum)
    members = list(base) if is_enum else []
    if members and not isinstance(members[0].value, str):
        return first  # int/other enum -> bare literal
    return f'"{first}"'


def _value(tp: object, seen: frozenset[type]) -> str:
    base = _unwrap_optional(tp)
    if _enum_values(base):
        return _enum_literal(base)  # type: ignore[arg-type]
    origin = get_origin(base)
    if origin in (list, set):
        args = get_args(base)
        item = _value(args[0], seen) if args else '"example"'
        if "\n" in item:
            inner = _continuation_indent(item, _INDENT)
            return f"[\n{_INDENT}{inner},\n]"
        return f"[{item}]"
    if isinstance(base, type) and issubclass(base, BaseModel):
        return _model_expr(base, seen)
    if isinstance(base, type) and issubclass(base, datetime.date):
        return '"2026-01-01T00:00:00Z"'
    if isinstance(base, type):
        for typ, literal in _SCALARS.items():
            if base is typ:
                return literal
    return '"example"'


def _model_expr(model: type[BaseModel], seen: frozenset[type]) -> str:
    if model in seen:
        return f"{model.__name__}(...)"
    seen = seen | {model}
    if _is_wrapper(model):
        variant = _pick_variant(model, None)
        return _model_expr(variant, seen) if variant else f"{model.__name__}(...)"
    lines = [f"{model.__name__}("]
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        value = _continuation_indent(_value(field.annotation, seen), _INDENT)
        lines.append(f"{_INDENT}{name}={value},")
    lines.append(")")
    return "\n".join(lines)


def synthesize_body(model: type[BaseModel], *, variant: str | None = None) -> str:
    """Real-shaped constructor expression for ``model`` (required fields only)."""
    if _is_wrapper(model):
        chosen = _pick_variant(model, variant)
        if chosen is not None:
            return _model_expr(chosen, frozenset({model}))
        return f"{model.__name__}(...)"
    return _model_expr(model, frozenset())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_examples.py -v`
Expected: PASS (4 tests). The Step 1 hard-coded expected strings were verified against the real synthesizer output and should pass as-is — keep them as the primary oracle. The structural invariants (`"note" not in out`, `"strict_mode" not in out`, the cycle shape, the `startswith(...)` variant pick) are the independent oracles; only reconcile a hard-coded string if a pure-formatting detail differs, never to paper over a behavior change.

- [ ] **Step 5: Run ruff + mypy on the new module**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run ruff check src/phantasos/generator/sdk/examples.py && UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run mypy src/phantasos/generator/sdk/examples.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/sdk/examples.py tests/test_sdk_docs_examples.py
git commit -m "feat(sdk): add type-driven CRUD example synthesizer"
```

---

### Task 4: DocsConfig — showcase_variant + manual-override hatch

Adds the two new `sdk.yml` `docs:` options: `showcase_variant` (which oneOf variant the body example instantiates) and `examples` (per-slot verbatim override).

**Files:**
- Modify: `src/phantasos/productconfig.py:42-59`
- Test: `tests/test_productconfig.py`

**Interfaces:**
- Produces: `DocsExamples` (`extra="forbid"`, not frozen — consistent with the sibling `DocsOperations`; fields `create/read/list/update/delete: str | None = None`); `DocsConfig.examples: DocsExamples | None = None`; `DocsConfig.showcase_variant: str | None = None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_productconfig.py` (use the module's existing config-loading helper; if it loads from a YAML string/path, mirror that pattern):

```python
def test_docs_examples_and_variant_parse() -> None:
    from phantasos.productconfig import DocsConfig

    cfg = DocsConfig.model_validate(
        {
            "showcase_resource": "applications",
            "showcase_variant": "CustomApplicationInput",
            "examples": {"create": "created = client.applications.create_application(...)"},
        }
    )
    assert cfg.showcase_variant == "CustomApplicationInput"
    assert cfg.examples is not None
    assert cfg.examples.create.startswith("created =")
    assert cfg.examples.read is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_productconfig.py::test_docs_examples_and_variant_parse -v`
Expected: FAIL (`extra fields not permitted` for `examples`/`showcase_variant`).

- [ ] **Step 3: Implement the model changes**

In `src/phantasos/productconfig.py`, add a `DocsExamples` model just before `DocsConfig` and extend `DocsConfig`:

```python
class DocsExamples(BaseModel):
    """Optional per-slot verbatim override of the showcase CRUD example block."""

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
    showcase_variant: str | None = None
    site_name: str | None = None
    operations: DocsOperations | None = None
    examples: DocsExamples | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_productconfig.py::test_docs_examples_and_variant_parse -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(sdk): add docs.showcase_variant + docs.examples to product config"
```

---

### Task 5: Wire the synthesizer into the docs context

Resolves each body arg's model class from the imported SDK package, synthesizes `body_code`, and threads the per-slot `example_override`. Keeps `shape_context` testable without a real SDK: a missing/None resolver falls back to the old `Model(...)` placeholder.

**Files:**
- Modify: `src/phantasos/generator/sdk/docs.py:78-178`
- Test: `tests/test_cli_docs.py` (or `tests/test_sdk_docs_examples.py`)

**Interfaces:**
- Consumes: `synthesize_body` (Task 3); `DocsConfig.examples`, `DocsConfig.showcase_variant` (Task 4).
- Produces: each body entry in `operations[slot].required_args` gains `"body_code": str` (synthesized expression, or `f"{body_model}(...)"` fallback); each `operations[slot]` gains `"example_override": str | None`. `shape_context` gains keyword args `resolve: Callable[[str], type | None] | None = None` and `variant: str | None = None`, and `examples: DocsExamples | None = None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli_docs.py` (import `shape_context` + `OperationInventory`/`OperationInfo`/`ParamInfo` from `phantasos.generator.cli.inventory`; mirror that module's existing fixtures):

```python
def test_shape_context_synthesizes_body_code_and_override() -> None:
    import datetime
    from pydantic import BaseModel, Field, StrictStr
    from phantasos.generator.cli.inventory import (
        OperationInfo, OperationInventory, ParamInfo,
    )
    from phantasos.productconfig import DocsExamples
    from phantasos.generator.sdk.docs import shape_context

    class AppInput(BaseModel):
        name: StrictStr = Field(description="Name")
        created_at: datetime.datetime

    # OperationInventory requires sdk_package/sdk_version (no defaults, extra="forbid").
    inv = OperationInventory(sdk_package="p", sdk_version="1", operations=[
        OperationInfo(
            resource="apps", method="create_app",
            params=[ParamInfo(name="body", annotation="AppInput",
                              location="body", required=True, body_model="AppInput")],
        )
    ])
    ctx = shape_context(
        inv, resource="apps", site_name="x", auth=None, overrides=None,
        has_pagination=False, resolve={"AppInput": AppInput}.get, variant=None,
        examples=DocsExamples(create='X = 1'),
    )
    op = ctx["showcase"]["operations"]["create"]
    body = next(a for a in op["required_args"] if a["kind"] == "body")
    assert body["body_code"].startswith("AppInput(")
    assert 'name="example"' in body["body_code"]
    assert op["example_override"] == "X = 1"


def test_shape_context_falls_back_without_resolver() -> None:
    from phantasos.generator.cli.inventory import (
        OperationInfo, OperationInventory, ParamInfo,
    )
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(sdk_package="p", sdk_version="1", operations=[
        OperationInfo(resource="apps", method="create_app",
                      params=[ParamInfo(name="body", annotation="AppInput",
                                        location="body", required=True, body_model="AppInput")])
    ])
    ctx = shape_context(inv, resource="apps", site_name="x", auth=None,
                        overrides=None, has_pagination=False)
    body = next(a for a in ctx["showcase"]["operations"]["create"]["required_args"]
                if a["kind"] == "body")
    assert body["body_code"] == "AppInput(...)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_cli_docs.py -k "synthesize_body_code or falls_back_without_resolver" -v`
Expected: FAIL (`shape_context` has no `resolve`/`examples` kwargs; `body_code` missing).

- [ ] **Step 3: Update `_op_dict` and `shape_context` in `docs.py`**

Change `_op_dict` to accept a resolver + variant and attach `body_code`:

```python
def _op_dict(
    op: OperationInfo,
    resolve: "Callable[[str], type | None] | None",
    variant: str | None,
) -> dict[str, object]:
    from .examples import synthesize_body

    required_args: list[dict[str, object]] = []
    for p in op.params:
        if not p.required:
            continue
        if p.location == "body":
            cls = resolve(p.body_model) if (resolve and p.body_model) else None
            body_code = (
                synthesize_body(cls, variant=variant)
                if cls is not None
                else f"{p.body_model}(...)"
            )
            required_args.append(
                {
                    "name": p.name,
                    "kind": "body",
                    "body_model": p.body_model,
                    "body_code": body_code,
                }
            )
        elif p.location == "path":
            placeholder = p.enum_values[0] if p.enum_values else f"<{p.name}>"
            required_args.append(
                {
                    "name": p.name,
                    "kind": "path",
                    "placeholder": str(placeholder),
                }
            )
    return {
        "method": op.method,
        "summary": op.summary,
        "description": op.description,
        "required_args": required_args,
        "return_model": op.return_model,
        "items_field": op.items_field,
    }
```

Add `Callable` to the `typing` import. Update `shape_context`'s signature and body:

```python
def shape_context(
    inventory: OperationInventory,
    *,
    resource: str,
    site_name: str,
    auth: object | None,
    overrides: DocsOperations | None,
    has_pagination: bool,
    resolve: "Callable[[str], type | None] | None" = None,
    variant: str | None = None,
    examples: "DocsExamples | None" = None,
) -> dict[str, object]:
    ops = [op for op in inventory.operations if op.resource == resource]
    slots = classify_operations(ops, resource, overrides)
    operations = {slot: _op_dict(op, resolve, variant) for slot, op in slots.items()}
    ex = vars(examples) if examples else {}
    for slot, entry in operations.items():
        entry["example_override"] = ex.get(slot)
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
    # ... credentials block unchanged ...
```

Add the `DocsExamples` import under `TYPE_CHECKING` and `from collections.abc import Callable` to the runtime imports.

- [ ] **Step 4: Update `build_docs_context` to pass a resolver, variant, and examples**

In `build_docs_context`, after `inventory = introspect(...)`:

```python
    import importlib

    models_ns = importlib.import_module(f"{cfg.package}.models")

    def _resolve(name: str) -> type | None:
        obj = getattr(models_ns, name, None)
        return obj if isinstance(obj, type) else None

    return shape_context(
        inventory,
        resource=cfg.docs.showcase_resource,
        site_name=str(site_name),
        auth=loaded.auth,
        overrides=cfg.docs.operations,
        has_pagination=bool(loaded.context.get("has_pagination")),
        resolve=_resolve,
        variant=cfg.docs.showcase_variant,
        examples=cfg.docs.examples,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_cli_docs.py -k "synthesize_body_code or falls_back_without_resolver" -v`
Expected: PASS.

- [ ] **Step 6: Run the full docs-context test module + mypy**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_cli_docs.py -v && UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run mypy src/phantasos/generator/sdk/docs.py`
Expected: PASS / clean.

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/generator/sdk/docs.py tests/test_cli_docs.py
git commit -m "feat(sdk): synthesize CRUD body examples + thread manual override into docs context"
```

---

### Task 6: Templates consume body_code + example_override

Swaps the opaque `{{ body_model }}(...)` placeholder for the synthesized `body_code` and adds the per-slot verbatim override branch, in both the CRUD guide and the Getting-Started read-fallback.

**Files:**
- Modify: `src/phantasos/scaffold/docs/guides/crud.md.jinja`
- Modify: `src/phantasos/scaffold/docs/getting-started.md.jinja:33`
- Test: `tests/test_sdk_docs_emitted.py`

**Interfaces:**
- Consumes: `operations[slot].example_override`, `operations[slot].required_args[*].body_code` (Task 5). Note: the emission tests build the context **by hand** and must now supply `body_code`/`example_override` in fixtures.

- [ ] **Step 1: Update the emission-test fixture + expectations**

In `tests/test_sdk_docs_emitted.py`, update `_ctx()`'s create op body arg (lines 59-64) to include `body_code` and add `example_override: None` to each op; and add coverage for both branches:

```python
# in _ctx(), the create body arg:
{
    "name": "create_or_replace_app_input",
    "kind": "body",
    "body_model": "CreateOrReplaceAppInput",
    "body_code": 'CustomApplicationInput(\n    name="example",\n)',
},
# and give every operation entry: "example_override": None
```

Add tests:

```python
def test_crud_renders_synthesized_body_code(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    assert "CustomApplicationInput(" in crud
    assert 'name="example"' in crud
    assert "CreateOrReplaceAppInput(...)" not in crud  # no opaque placeholder


def test_crud_uses_manual_override_verbatim(tmp_path: Path) -> None:
    ctx = _ctx()
    ctx["showcase"]["operations"]["create"]["example_override"] = (
        "created = client.applications.create_application(MAGIC)"
    )
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, ctx)
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    assert "MAGIC" in crud
    assert 'name="example"' not in crud  # override replaced the whole call
```

Also update `test_getting_started_handles_read_body_arg` (line 143): give the read body arg `"body_code": "ThingQuery()"` and assert `"thing_query=ThingQuery()"` instead of `ThingQuery(...)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py -v`
Expected: FAIL (templates still emit `body_model(...)`; no override branch).

- [ ] **Step 3: Rewrite `crud.md.jinja` Create/Read/Update/Delete blocks**

For each of the four sections in `src/phantasos/scaffold/docs/guides/crud.md.jinja`, wrap the fenced example with the override branch and use `body_code`. The Create block becomes (apply the same shape to read/update/delete, swapping the verb, slot key, and assignment target — `created`/`fetched`/`updated`/none):

```jinja
{% if showcase.has_create %}
## Create

```python
{% if ops["create"].example_override %}{{ ops["create"].example_override }}{% else %}created = client.{{ showcase.attr }}.{{ ops["create"].method }}(
{% for a in ops["create"].required_args %}{% if a.kind == "body" %}    {{ a.name }}={{ a.body_code | indent(4) }},
{% else %}    {{ a.name }}="{{ a.placeholder }}",
{% endif %}{% endfor %}){% endif %}
```
{% endif %}
```

(For the Delete block there is no assignment target — keep `client.{{ showcase.attr }}.{{ ops["delete"].method }}(` as today; only the body line and override branch change.)

- [ ] **Step 4: Update `getting-started.md.jinja` read-fallback (line 33)**

Replace `{{ a.body_model }}(...)` with `{{ a.body_code }}`. (Read ops rarely carry a body arg; this inline slot assumes a single-line `body_code` — a multi-line body here would render flush-left inside the call. Acceptable given the rarity; revisit with an `indent` filter only if a real read op needs it.)

```jinja
result = client.{{ showcase.attr }}.{{ showcase.operations["read"].method }}({% for a in showcase.operations["read"].required_args %}{% if a.kind == "body" %}{{ a.name }}={{ a.body_code }}{% else %}{{ a.name }}="{{ a.placeholder }}"{% endif %}{% if not loop.last %}, {% endif %}{% endfor %})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_docs_emitted.py -v`
Expected: PASS (all, including the updated getting-started + colon-YAML tests).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/scaffold/docs/guides/crud.md.jinja src/phantasos/scaffold/docs/getting-started.md.jinja tests/test_sdk_docs_emitted.py
git commit -m "feat(sdk): render real CRUD examples + manual-override hatch in docs templates"
```

---

### Task 7: Dogfood curated example, integration-gate assertions, deep-dive + CHANGELOG

End-to-end validation on the real prisma-browser SDK plus the showcase polish and required docs.

**Files:**
- Modify: `products/prisma-browser/sdk.yml:12-13` (docs block)
- Modify: `noxfile.py` (`sdk-docs` session, after line 230)
- Modify: `.agents/context/sdk-generator.md`, `.agents/context/scaffold.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add the curated create example to prisma-browser**

In `products/prisma-browser/sdk.yml`, extend the `docs:` block (currently `showcase_resource: applications`). Draft a schema-valid `CustomApplicationInput` (the URL must satisfy the normalization rules in `UrlInput.url`'s description):

```yaml
docs:
  showcase_resource: applications
  showcase_variant: CustomApplicationInput
  examples:
    create: |
      created = client.applications.create_application(
          type="custom",
          create_or_replace_app_input=CustomApplicationInput(
              name="Acme Wiki",
              type="custom",
              urls=[UrlInput(url="https://wiki.acme.com/*")],
          ),
      )
```

- [ ] **Step 2: Add positive assertions to the `sdk-docs` gate**

In `noxfile.py`, replace the final check (line 229-230) of the `sdk_docs` session with end-to-end assertions on the built `site/`:

```python
    site = out / "site"
    if not (site / "reference").exists():
        session.error("reference pages were not generated")
    # (A) griffe-pydantic surfaces field descriptions on a leaf model page
    leaf = (site / "reference/models/custom_application_input/index.html")
    if not (leaf.exists() and "Name of the application" in leaf.read_text()):
        session.error("model field descriptions did not render (griffe-pydantic)")
    # (B) oneOf wrapper page links its variant models
    wrapper = (site / "reference/models/create_or_replace_app_input/index.html")
    if not (wrapper.exists() and "CustomApplicationInput" in wrapper.read_text()):
        session.error("oneOf wrapper page is missing variant links")
    # (C) the curated CRUD example rendered (not the opaque placeholder)
    crud = (site / "guides/crud/index.html")
    txt = crud.read_text() if crud.exists() else ""
    if "Acme Wiki" not in txt or "CreateOrReplaceAppInput(...)" in txt:
        session.error("CRUD create example did not render the curated body")
```

(Confirm the built HTML paths with `ls out/site/reference/models/` during Step 4; mkdocs `use_directory_urls` may emit `.../custom_application_input/index.html` — adjust the literal paths if the dir layout differs.)

- [ ] **Step 3: Run the integration gate (needs the OAG JRE + network)**

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s sdk-docs`
Expected: PASS — `mkdocs build --strict` succeeds and all three assertions pass. If `--strict` fails on new autoref/duplicate warnings, adjust `mkdocs.yml` `filters` (Task 1) or the gen_ref variant-link approach (Task 2) until clean; show the real output before claiming green.

- [ ] **Step 4: Update the subsystem deep-dive narrative**

Edit `.agents/context/sdk-generator.md` (docs stage, "step 4b") and `.agents/context/scaffold.md` (Docs row): describe griffe-pydantic field rendering, oneOf wrapper variant-link pages, the example synthesizer (`generator/sdk/examples.py`), and the `docs.showcase_variant` / `docs.examples` config. Then refresh generated blocks:

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s context && UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s context -- --check`
Expected: second run passes (no drift).

- [ ] **Step 5: Add CHANGELOG entries**

Under `## [Unreleased]` in `CHANGELOG.md`, add:

```markdown
### Added
- Generated SDK docs now render each pydantic model's full field surface (via
  `griffe-pydantic`), document oneOf wrapper types as links to their variant
  models, and emit real-shaped CRUD examples synthesized from the schema.
- `sdk.yml` `docs:` gains `showcase_variant` (choose the oneOf variant used in
  the example) and `examples.<slot>` (verbatim per-operation example override).
```

- [ ] **Step 6: Phase-boundary validation**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s gate`
Expected: PASS (offline gate — full test suite + lint + types + context check).

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s live`
Expected: PASS or SKIP (skips without tenant credentials — record which).

- [ ] **Step 7: Commit**

```bash
git add products/prisma-browser/sdk.yml noxfile.py .agents/context/sdk-generator.md .agents/context/scaffold.md CHANGELOG.md
git commit -m "test(sdk): dogfood curated example + assert docs fidelity in the sdk-docs gate"
```

---

## Self-Review Notes

- **Spec coverage:** Issue 1 (model fields) → Tasks 1, 2, 6(assert A/B). Issue 2 (real examples) → Tasks 3, 4, 5, 6. Manual override → Tasks 4, 5, 6. Configurable oneOf variant → Tasks 3, 4, 5. oneOf wrapper pages → Task 2. show-all-fields + aggressive filter → Task 1.
- **Type consistency:** `synthesize_body(model, *, variant=None) -> str` (Task 3) is consumed in `_op_dict` (Task 5). `body_code` (str) and `example_override` (str|None) flow context→template (Tasks 5→6). `DocsExamples`/`showcase_variant` (Task 4) consumed by `build_docs_context` (Task 5) and `sdk.yml` (Task 6).
- **Risk — `--strict`:** enabling `show_if_no_docstring` + griffe-pydantic can surface new autoref warnings that `--strict` promotes to errors. The `sdk-docs` gate (Task 6 Step 3) is the catch; mitigation is filter/inventory tuning, not loosening `--strict`.
- **Risk — HTML paths:** Task 6 assertions assume `use_directory_urls` (`.../index.html`). Verify the real layout in Step 4 before finalizing the literals.
