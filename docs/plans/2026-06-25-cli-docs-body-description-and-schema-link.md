# CLI docs: nested-model Description + clickable schema link — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the generated CLI MkDocs command reference, fill the empty **Description** cell for a nested-model body flag (e.g. `--microsoft` → `CreateMicrosoftProviderRequest`) with the model's schema-level description, and turn the **Type** cell into a clickable link that jumps to that flag's schema disclosure block below.

**Architecture:** Two independent IR/render fixes, both generate-time and pure (no live CLI import, no mkdocstrings):
1. **Description** — capture the SDK model's class docstring (openapi-generator writes the OpenAPI component-schema `description` there) onto `ModelSchema.description` in the registry, then have the docs context fall back to it when a model-ref row carries no field-level description of its own.
2. **Link** — the docs context emits a per-page-unique anchor slug for each nested-model flag; the markdown template renders the Type cell as a link to that slug and emits a matching `<a id=...>` immediately above the `??? note` schema block.

**Tech Stack:** Python 3.12+, pydantic v2, Jinja2 templates, MkDocs Material (`pymdownx.details`, `attr_list`), pytest, uv, nox, ruff.

## Global Constraints

- **Separation of duty:** the CLI registry walk lives in `cli/modelschema.py` and emits the CLI's own `ModelField`/`ModelSchema`. Do NOT push description logic into `opmodel/` (shared `FieldInfo`/`OperationInfo` stay untouched — spec D8). The SDK docs path (`generator/sdk/docs.py`) is NOT reused.
- **IR-driven, generate-time:** the command reference is a pure function of `CliIR`; no live CLI import, no mkdocstrings (see `docs/adr/0001-cli-docs-ir-driven-generate-time.md`).
- **Frozen oracles:** never edit any `protected_globs` path from `.claude/harness.toml` (`products/*/overrides/tests/test_sdk_crud_live.py*`, `tests/acceptance/**`, `.claude/harness.toml`, `.claude/hooks/**`, `.claude/settings.json`). `tests/fixtures/fakesdk/**` is NOT protected and may be edited.
- **Evidence before assertions:** run each test and show real output before claiming pass. Run `uv run nox -s live` (skips without creds) before declaring done; the offline gate (`uv run nox -s gate`) runs on stop.
- **Env (this machine):** prefix uv with `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos` and, for venv-backed nox sessions, `NOX_ENVDIR=$HOME/.tmp/phantasos-nox`.
- **Branch/CHANGELOG:** work on `feature/cli-payload-helper`; squash-merge into `develop`; NO version bump; record under `## [Unreleased]` in `CHANGELOG.md`.

---

## File Structure

- `src/phantasos/generator/cli/ir.py` — add `description: str = ""` to `ModelSchema` (the only new IR field).
- `src/phantasos/generator/cli/modelschema.py` — add `_model_doc(cls)`; populate `ModelSchema.description` in both `_model_to_schema` branches.
- `src/phantasos/generator/cli/docs.py` — add `_model_desc()` fallback + `_anchor()` slug; wire description fallback into `_flag_row`/`_schema_rows`; add `type_anchor` to `_flag_row`; thread `key=` from `_command_view`.
- `src/phantasos/generator/cli/templates/docs/reference_object.md.jinja` — render Type cell as a link when `type_anchor` set; emit `<a id=...>` above the `??? note` schema block.
- `tests/cli/test_modelschema.py` — NEW: unit tests for registry description capture.
- `tests/cli/test_docs_context.py` — add unit tests for description fallback + `type_anchor`.
- `tests/cli/test_docs_emitted.py` — add emitted-markdown tests for the rendered link + anchor + nested description.
- `tests/fixtures/fakesdk/fakesdk/models.py` — add a class docstring to `Contact` for the deterministic end-to-end description test.
- `CHANGELOG.md` — `## [Unreleased]` entry.
- `.agents/context/` — refresh the CLI-docs deep-dive narrative + generated blocks.

---

### Task 1: Capture the model-level description into the registry

The schema-level description ("Request body to create a Microsoft OneDrive provider.") is written by openapi-generator as the model's **class docstring**. For a model with NO description, the docstring is exactly the class name (verified: 252 prose vs 172 class-name docstrings across the prisma-browser SDK). Capture it onto `ModelSchema.description`, dropping the class-name-only case.

**Files:**
- Modify: `src/phantasos/generator/cli/ir.py:196-204` (`ModelSchema`)
- Modify: `src/phantasos/generator/cli/modelschema.py:54-115` (`_model_to_schema`)
- Test: `tests/cli/test_modelschema.py` (new)

**Interfaces:**
- Produces: `ModelSchema.description: str` (default `""`), populated from `cls.__doc__` via `_model_doc(cls: type[BaseModel]) -> str`.

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_modelschema.py`:

```python
"""Unit tests for the CLI model registry walk (modelschema.py)."""

from __future__ import annotations

from pydantic import BaseModel

from phantasos.generator.cli.modelschema import registry_from_models


class CreateMicrosoftProviderRequest(BaseModel):
    """
    Request body to create a Microsoft OneDrive provider.
    """

    tenant_id: str


class CreateOrReplaceAppGroupInput(BaseModel):  # no real docstring below
    """CreateOrReplaceAppGroupInput"""

    name: str


def test_registry_captures_model_level_description() -> None:
    reg = registry_from_models([CreateMicrosoftProviderRequest])
    assert (
        reg["CreateMicrosoftProviderRequest"].description
        == "Request body to create a Microsoft OneDrive provider."
    )


def test_registry_drops_classname_only_docstring() -> None:
    # openapi-generator emits `"""<ClassName>"""` for description-less schemas;
    # that is noise, not a description, so it must NOT be captured.
    reg = registry_from_models([CreateOrReplaceAppGroupInput])
    assert reg["CreateOrReplaceAppGroupInput"].description == ""


def test_model_doc_extraction_cases() -> None:
    # Direct coverage of the extraction helper that BOTH ModelSchema(...) sites use
    # (the regular branch AND the is_oneof branch thread the identical _model_doc(cls)).
    from phantasos.generator.cli.modelschema import _model_doc

    class Described(BaseModel):
        """
        Multi word

        description here.
        """

    class NameOnly(BaseModel):
        """NameOnly"""

    class NoDoc(BaseModel):
        pass

    assert _model_doc(Described) == "Multi word description here."  # whitespace collapsed
    assert _model_doc(NameOnly) == ""  # class-name-only docstring dropped
    assert _model_doc(NoDoc) == ""  # __doc__ is None (not inherited from BaseModel)
```

> The `is_oneof` branch (`modelschema.py:77`) threads the **same** `description=_model_doc(cls)` call as the regular branch (`:115`); `test_model_doc_extraction_cases` therefore covers the extraction logic for both. A synthetic oneOf wrapper is not worth constructing inline.

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_modelschema.py -v`
Expected: FAIL — `ModelSchema` has no `description` (pydantic `extra="forbid"` would also reject it if set), or `AttributeError`/assertion mismatch.

- [ ] **Step 3: Add the `description` field to `ModelSchema`**

In `src/phantasos/generator/cli/ir.py`, `ModelSchema` (lines 196-204) becomes:

```python
class ModelSchema(BaseModel):
    """A body model's field surface, stored deduped under a key in `CliIR.models`."""

    model_config = ConfigDict(extra="forbid")

    fields: list[ModelField]
    # True for a oneOf wrapper model whose `fields` ARE its variants.
    is_oneof: bool = False
    # The model's own schema-level description (openapi component `description`,
    # captured from the generated model's class docstring). "" when absent.
    description: str = ""
```

- [ ] **Step 4: Capture the docstring in `_model_to_schema`**

In `src/phantasos/generator/cli/modelschema.py`, add the helper near the top (after the imports, before `_resolve_ref`):

```python
def _model_doc(cls: type[BaseModel]) -> str:
    """The model's schema-level description from its class docstring.

    openapi-generator writes the OpenAPI component `description` as the class
    docstring; for a description-less schema it writes the bare class name. The
    latter is noise, so drop it. Whitespace (the indented triple-quote block) is
    collapsed to a single line.
    """
    doc = (cls.__doc__ or "").strip()
    if not doc or doc == cls.__name__:
        return ""
    return " ".join(doc.split())
```

Then thread it into BOTH `ModelSchema(...)` constructions. The oneOf branch (currently line 77):

```python
        return ModelSchema(fields=fields, is_oneof=True, description=_model_doc(cls)), children
```

The regular branch (currently line 115):

```python
    return ModelSchema(fields=fields, description=_model_doc(cls)), children
```

- [ ] **Step 5: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_modelschema.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/ir.py src/phantasos/generator/cli/modelschema.py tests/cli/test_modelschema.py
git commit -m "feat(cli-docs): capture model-level description into the registry"
```

---

### Task 2: Fall back to the model description in the docs context

The Body-table Description cell reads each row's own description (`Flag.help` for flags, `ModelField.description` for schema rows). For a bare-`$ref` property both are empty, because the description lives on the referenced model. Fall back to `ModelSchema.description` from Task 1.

**Files:**
- Modify: `src/phantasos/generator/cli/docs.py` (`_schema_rows` 116-158, `_flag_row` 161-174)
- Test: `tests/cli/test_docs_context.py`

**Interfaces:**
- Consumes: `ModelSchema.description` (Task 1).
- Produces: `_model_desc(models, ref) -> str` helper in `docs.py`; `_flag_row`/`_schema_rows` `help` cells now fall back to it.

- [ ] **Step 1: Write the failing test**

Append to `tests/cli/test_docs_context.py`:

```python
def test_nested_model_flag_help_falls_back_to_model_description() -> None:
    from phantasos.generator.cli.ir import ModelField, ModelSchema

    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="provider",
                key="create:provider",
                sdk_resource="providers",
                body_flags=[
                    Flag(
                        name="--microsoft",
                        param="microsoft",
                        py_type="CreateMicrosoftProviderRequest",
                        kind="json",
                        required=False,
                        help="",  # bare $ref property: no field-level description
                        model_ref="CreateMicrosoftProviderRequest",
                    )
                ],
            )
        ],
        models={
            "CreateMicrosoftProviderRequest": ModelSchema(
                description="Request body to create a Microsoft OneDrive provider.",
                fields=[
                    ModelField(
                        name="tenant_id",
                        alias="tenantId",
                        py_type="str",
                        kind="scalar",
                        required=True,
                        description="Azure AD tenant ID.",
                    )
                ],
            )
        },
    )
    ctx = build_cli_docs_context(
        ir, CliDocsConfig(showcase_object="provider"), distribution="acmecli", site_name="x"
    )
    row = cast(
        "list[dict[str, object]]",
        _commands(_objects(ctx)[0])[0]["body_flags"],
    )[0]
    assert row["help"] == "Request body to create a Microsoft OneDrive provider."


def test_model_description_fallback_is_pipe_and_newline_escaped() -> None:
    # The fallback source (model description) must be escaped for a GFM cell just like
    # field-level help is (mirrors test_flag_help_pipe_escaped_for_markdown_table).
    from phantasos.generator.cli.ir import ModelField, ModelSchema

    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="provider",
                key="create:provider",
                sdk_resource="providers",
                body_flags=[
                    Flag(
                        name="--cfg",
                        param="cfg",
                        py_type="Cfg",
                        kind="json",
                        required=False,
                        help="",
                        model_ref="Cfg",
                    )
                ],
            )
        ],
        models={
            "Cfg": ModelSchema(
                description="pick a | b\nor c",
                fields=[
                    ModelField(
                        name="x", alias="x", py_type="str", kind="scalar", required=True
                    )
                ],
            )
        },
    )
    ctx = build_cli_docs_context(
        ir, CliDocsConfig(showcase_object="provider"), distribution="acmecli", site_name="x"
    )
    row = cast("list[dict[str, object]]", _commands(_objects(ctx)[0])[0]["body_flags"])[0]
    assert row["help"] == "pick a \\| b or c"  # pipe escaped, newline -> space
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_context.py::test_nested_model_flag_help_falls_back_to_model_description -v`
Expected: FAIL — `row["help"] == ""` (no fallback yet).

- [ ] **Step 3: Add the fallback helper and wire it in**

In `src/phantasos/generator/cli/docs.py`, add the helper above `_schema_rows` (after `_clean_description`). Named `_ref_description` (NOT `_model_desc`) to avoid a one-character collision with `modelschema._model_doc`, which they are easy to confuse with:

```python
def _ref_description(models: dict[str, ModelSchema] | None, ref: str | None) -> str:
    """The schema-level description of a referenced model, or "" when absent."""
    m = models.get(ref) if models and ref else None
    return m.description if m else ""
```

In `_schema_rows`, change the `help` line (currently line 150) from `"help": _cell(mf.description),` to:

```python
                "help": _cell(mf.description or _ref_description(models, mf.model_ref)),
```

In `_flag_row`, change the `help` line (currently line 172) from `"help": _cell(f.help),` to:

```python
        "help": _cell(f.help or _ref_description(models, f.model_ref)),
```

This fallback applies **recursively** (it is wired into `_schema_rows`, not just the top-level body flags): a nested field at any depth that lacks its own description inherits its referenced model's description. That is the intended fix for the `contact` → `Contact` case in Task 5, and is a deliberate, page-wide behavior — not just the headline `--microsoft` row.

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_context.py -v`
Expected: PASS (the new test + all existing tests in the file).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/docs.py tests/cli/test_docs_context.py
git commit -m "feat(cli-docs): fall back to model description for nested-model flag help"
```

---

### Task 3: Emit a per-page-unique schema anchor in the docs context

The Type cell must link to the flag's `??? note` schema block. Compute a stable, page-unique anchor slug for each nested-model flag and expose it on the row as `type_anchor` (`None` when the flag has no schema block).

**Uniqueness rationale (the axis that actually occurs):** the dominant collision is the *same flag across multiple commands on one page*, not multiple model-ref flags in one command. On the fakesdk widget page, `--profile` (→ `WidgetProfile`) rides on `create_widget`, `update_widget`, `patch_widget`, and the `revoke`/`suspend` actions, so the `WidgetProfile` schema block — and now its `<a id>` — renders **several times on one page**. Embedding `Command.key` in the slug keeps each distinct (`create-widget-profile-schema`, `update-widget-profile-schema`, `request-widget-revoke-profile-schema`, …). The real prisma-browser `--microsoft`/`--google`-in-one-command case is also covered, but is the easier axis.

**Files:**
- Modify: `src/phantasos/generator/cli/docs.py` (`_flag_row` 161-174, `_command_view` 177-210)
- Test: `tests/cli/test_docs_context.py`

**Interfaces:**
- Consumes: `Command.key` (canonical `"verb:object[:variant_or_action]"`).
- Produces: `_anchor(key, flag_name) -> str`; each flag row dict gains `"type_anchor": str | None`. `_flag_row` signature gains a keyword-only `key: str = ""`.

- [ ] **Step 1: Write the failing test**

Append to `tests/cli/test_docs_context.py`:

```python
def test_nested_model_flag_carries_unique_type_anchor() -> None:
    from phantasos.generator.cli.ir import ModelField, ModelSchema

    def _msr(name: str) -> "ModelSchema":
        return ModelSchema(
            description=f"{name} desc",
            fields=[
                ModelField(
                    name="x", alias="x", py_type="str", kind="scalar", required=True
                )
            ],
        )

    def _json_flag(flag: str, ref: str) -> Flag:
        return Flag(
            name=flag,
            param=flag.lstrip("-").replace("-", "_"),
            py_type=ref,
            kind="json",
            required=False,
            model_ref=ref,
        )

    ir = CliIR(
        sdk_package="acme",
        sdk_version="1",
        commands=[
            Command(
                verb="create",
                object="cloud-storage-provider",
                key="create:cloud-storage-provider",
                sdk_resource="csp",
                body_flags=[
                    _json_flag("--microsoft", "CreateMicrosoftProviderRequest"),
                    _json_flag("--google", "CreateGoogleProviderRequest"),
                ],
            )
        ],
        models={
            "CreateMicrosoftProviderRequest": _msr("CreateMicrosoftProviderRequest"),
            "CreateGoogleProviderRequest": _msr("CreateGoogleProviderRequest"),
        },
    )
    ctx = build_cli_docs_context(
        ir,
        CliDocsConfig(showcase_object="cloud-storage-provider"),
        distribution="acmecli",
        site_name="x",
    )
    rows = cast(
        "list[dict[str, object]]", _commands(_objects(ctx)[0])[0]["body_flags"]
    )
    anchors = {cast("dict[str, object]", r)["name"]: r["type_anchor"] for r in rows}
    assert anchors["--microsoft"] == "create-cloud-storage-provider-microsoft-schema"
    assert anchors["--google"] == "create-cloud-storage-provider-google-schema"


def test_scalar_flag_has_no_type_anchor() -> None:
    ctx = build_cli_docs_context(
        _ir(), CliDocsConfig(showcase_object="widget"), distribution="acmecli", site_name="x"
    )
    create = next(
        c for o in _objects(ctx) for c in _commands(o) if c["key"] == "create:widget"
    )
    row = cast("list[dict[str, object]]", create["body_flags"])[0]  # --name, scalar
    assert row["type_anchor"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_context.py::test_nested_model_flag_carries_unique_type_anchor tests/cli/test_docs_context.py::test_scalar_flag_has_no_type_anchor -v`
Expected: FAIL — `KeyError: 'type_anchor'`.

- [ ] **Step 3: Add `_anchor` and wire `type_anchor` + `key` threading**

In `src/phantasos/generator/cli/docs.py`, add the helper above `_flag_row` (`re` is already imported at line 12):

```python
def _anchor(key: str, flag_name: str) -> str:
    """Page-unique slug for a nested-model flag's schema disclosure block.

    Built from the command key + flag name so the same flag name under two
    commands on one reference page gets distinct anchors.
    """
    base = f"{key}-{flag_name.lstrip('-')}-schema".lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")
```

Change `_flag_row` (lines 161-174) to accept `key` and emit `type_anchor`. `key` is **required** keyword-only (no default): a forgotten call site then fails with `TypeError` at generate time rather than silently producing colliding `-…-schema` anchors (fail-loud, matching the "fail loud" validation style already in `docs.py`):

```python
def _flag_row(
    f: Flag, models: dict[str, ModelSchema] | None = None, *, key: str
) -> dict[str, object]:
    schema = None
    if f.kind == "json" and f.model_ref and models:
        schema = _schema_rows(models, f.model_ref)
    return {
        "name": f.name,
        "type": (f.model_ref or f.py_type),
        "type_anchor": _anchor(key, f.name) if schema else None,
        "required": f.required,
        "choices": [_cell(c) for c in f.choices] if f.choices else None,
        "help": _cell(f.help or _ref_description(models, f.model_ref)),
        "schema": schema,
    }
```

In `_command_view` (lines 201-204), pass `key=c.key` to all four `_flag_row` calls:

```python
        "path_flags": [_flag_row(f, models, key=c.key) for f in c.path_params],
        "body_flags": [_flag_row(f, models, key=c.key) for f in body],
        "filter_flags": [_flag_row(f, models, key=c.key) for f in filters],
        "pagination_flags": [_flag_row(f, models, key=c.key) for f in pagination],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_context.py -v`
Expected: PASS (new tests + all existing).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/docs.py tests/cli/test_docs_context.py
git commit -m "feat(cli-docs): emit page-unique schema anchor slug for nested-model flags"
```

---

### Task 4: Render the Type-cell link + schema anchor in the template

Make the Body/Arguments tables render the Type cell as a markdown link when `type_anchor` is set, and emit a matching `<a id=...>` immediately above each `??? note` schema block. A blank line between the anchor and `??? note` keeps python-markdown from swallowing the admonition into the raw-HTML block.

**Files:**
- Modify: `src/phantasos/generator/cli/templates/docs/reference_object.md.jinja:20-31` (`flag_table` macro)
- Test: `tests/cli/test_docs_emitted.py`

**Interfaces:**
- Consumes: row dicts with `type`, `type_anchor`, `schema`, `name` (Tasks 2-3).

- [ ] **Step 1: Write the failing test**

Append to `tests/cli/test_docs_emitted.py`:

```python
def test_reference_links_nested_model_type_to_schema_anchor(
    emit_cli: Callable[..., Path],
) -> None:
    import re

    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    # --profile is the WidgetProfile body flag; its command key is create:widget,
    # so the anchor slug is create-widget-profile-schema.
    anchor = "create-widget-profile-schema"
    # The Type cell is a markdown link to the anchor (code span inside the link text).
    assert f"[`WidgetProfile`](#{anchor})" in text
    # A matching anchor target sits immediately above the ??? note schema block.
    assert f'<a id="{anchor}"></a>' in text
    # mkdocs --strict does NOT validate intra-page fragments by default, so guard the
    # link<->anchor wiring directly: every WidgetProfile Type-cell link must point at an
    # <a id> that is actually emitted on the page (catches a future slug drift).
    link_slugs = set(re.findall(r"\[`WidgetProfile`\]\(#([a-z0-9-]+)\)", text))
    id_slugs = set(re.findall(r'<a id="([a-z0-9-]+-profile-schema)">', text))
    assert anchor in link_slugs and anchor in id_slugs
    assert link_slugs <= id_slugs, f"link slugs with no anchor: {link_slugs - id_slugs}"
    # The blank line between the <a id> and the ??? note is LOAD-BEARING: without it
    # python-markdown folds the admonition into the raw-HTML block. Assert it exactly.
    lines = text.splitlines()
    a = next(k for k, ln in enumerate(lines) if f'id="{anchor}"' in ln)
    assert lines[a + 1] == "", "missing load-bearing blank line after <a id>"
    assert lines[a + 2].startswith('??? note "`--profile` schema"')


def test_reference_schema_anchors_unique_per_page(emit_cli: Callable[..., Path]) -> None:
    import re

    # --profile (WidgetProfile) renders under several widget commands on one page; the
    # command-keyed slug must keep every <a id> distinct (no duplicate HTML ids), and
    # a non-create command must produce a DIFFERENT anchor (proves `key` threading).
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    ids = re.findall(r'<a id="([a-z0-9-]+)"></a>', text)
    assert len(ids) == len(set(ids)), f"duplicate anchor ids on page: {ids}"
    profile_ids = {i for i in ids if i.endswith("-profile-schema")}
    # WidgetProfile renders under >1 widget command, each with a distinct key-scoped slug.
    assert "create-widget-profile-schema" in profile_ids
    assert len(profile_ids) >= 2, f"expected per-command profile anchors, got {profile_ids}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_reference_links_nested_model_type_to_schema_anchor -v`
Expected: FAIL — Type cell is plain `` `WidgetProfile` `` and no `<a id>` is emitted.

- [ ] **Step 3: Update the `flag_table` macro**

In `src/phantasos/generator/cli/templates/docs/reference_object.md.jinja`, replace the `flag_table` macro (lines 20-31) with:

```jinja
{% macro flag_table(rows) -%}
| Flag | Type | Required | Description |
| --- | --- | --- | --- |
{% for f in rows -%}
| `{{ f.name }}` | {% if f.type_anchor %}[`{{ f.type }}`](#{{ f.type_anchor }}){% else %}`{{ f.type }}`{% endif %} | {{ "yes" if f.required else "no" }} | {{ f.help }}{% if f.choices %} _(values: {{ f.choices | join(", ") }})_{% endif %} |
{% endfor %}
{% for f in rows %}{% if f.schema %}
{# The blank line between <a id> and ??? note is LOAD-BEARING: without it
   python-markdown folds the admonition into the raw-HTML block. Do not remove. #}
<a id="{{ f.type_anchor }}"></a>

??? note "`{{ f.name }}` schema"

{{ schema_block(f.schema) | indent(4, first=True) }}
{% endif %}{% endfor %}
{%- endmacro -%}
```

- [ ] **Step 4: Run the test + the existing emitted/disclosure tests**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: PASS — the new link test plus `test_reference_page_per_object`, `test_reference_page_renders_nested_schema_disclosure`, and (if mkdocs is installed) `test_emitted_docs_build_strict`.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/docs/reference_object.md.jinja tests/cli/test_docs_emitted.py
git commit -m "feat(cli-docs): link Type cell to its schema disclosure block"
```

---

### Task 5: End-to-end description via fakesdk + strict-build verification

Prove the description fallback reaches the rendered markdown. The `contact` field of `WidgetProfile` has no field-level description, so giving `Contact` a class docstring makes the nested `--profile` schema table show it via the Task-2 fallback. Then verify the whole site builds under `mkdocs --strict` (the anchor + link must not break the build).

**Files:**
- Modify: `tests/fixtures/fakesdk/fakesdk/models.py` (`Contact`)
- Test: `tests/cli/test_docs_emitted.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/cli/test_docs_emitted.py`:

```python
def test_reference_nested_field_shows_model_description(
    emit_cli: Callable[..., Path],
) -> None:
    # WidgetProfile.contact has no field-level description; the Contact model's own
    # class docstring must surface in the nested --profile schema table (Task 2).
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))
    text = (out / "docs" / "reference" / "widget.md").read_text()
    assert "How to reach the widget owner." in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py::test_reference_nested_field_shows_model_description -v`
Expected: FAIL — `Contact` has no docstring, so the cell is empty.

- [ ] **Step 3: Give the `Contact` fixture model a docstring**

In `tests/fixtures/fakesdk/fakesdk/models.py`, change `Contact` from:

```python
class Contact(BaseModel):
    name: str  # required
    timezone: Optional[str] = None
```

to:

```python
class Contact(BaseModel):
    """How to reach the widget owner."""

    name: str  # required
    timezone: Optional[str] = None
```

- [ ] **Step 4: Run the new test + the full emitted suite**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run pytest tests/cli/test_docs_emitted.py -v`
Expected: PASS, including `test_emitted_docs_build_strict` if mkdocs is installed (the `--strict` build must succeed with the new anchor + intra-page link).

- [ ] **Step 5: Manually verify the strict build explicitly (anchor/link don't warn)**

Run:
```bash
UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run python - <<'PY'
import subprocess, tempfile, shutil, pathlib, sys
# Reuse the emit_cli path by emitting once and building --strict, printing output.
PY
```
If `mkdocs` is not on PATH, instead build the real product docs the user is viewing and confirm no warnings:
```bash
cd <emitted prisma-browser-cli dir> && UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos uv run mkdocs build --strict 2>&1 | tail -20
```
Expected: exit 0, no `WARNING` lines referencing the new anchors/links.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/fakesdk/fakesdk/models.py tests/cli/test_docs_emitted.py
git commit -m "test(cli-docs): end-to-end nested-model description in emitted reference"
```

---

### Task 6: CHANGELOG, context deep-dive refresh, and full gate

**Files:**
- Modify: `CHANGELOG.md` (`## [Unreleased]`)
- Modify: `.agents/context/` CLI-docs deep-dive (narrative + generated blocks)

- [ ] **Step 1: Add the CHANGELOG entry**

Under `## [Unreleased]` in `CHANGELOG.md`, add (match the existing list style):

```markdown
### Fixed
- CLI docs: nested-model body flags (e.g. `--microsoft`) now show the model's
  schema-level description in the Body table, and the Type cell links to that
  flag's schema disclosure block.
```

- [ ] **Step 2: Update the CLI generator deep-dive**

The relevant deep-dive is `.agents/context/cli-generator.md` (there is no separate `cli-docs` file; confirm via `.agents/context/index.md`). It has **no** `BEGIN GENERATED` blocks tied to `ModelSchema`/`_flag_row`, so this is a narrative-only edit. Update its narrative to note: `ModelSchema.description` now carries the model's class-docstring description; `_flag_row`/`_schema_rows` fall back to it for empty cells; the Type cell links to a per-flag `<a id>` anchor (slug `_anchor(key, flag)`) emitted above the `??? note` block. If no such file exists, do NOT fabricate one — flag it and skip.

- [ ] **Step 3: Refresh generated context blocks**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos NOX_ENVDIR=$HOME/.tmp/phantasos-nox uv run nox -s context`
Then verify: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos NOX_ENVDIR=$HOME/.tmp/phantasos-nox uv run nox -s context -- --check`
Expected: `--check` passes (no diff).

- [ ] **Step 4: Run the full offline gate**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos NOX_ENVDIR=$HOME/.tmp/phantasos-nox uv run nox -s gate`
Expected: PASS (lint, type, tests).

- [ ] **Step 5: Run live CRUD validation (skips without creds)**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/phantasos NOX_ENVDIR=$HOME/.tmp/phantasos-nox uv run nox -s live`
Expected: PASS or SKIP (no tenant credentials) — no failures.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md .agents/context
git commit -m "docs(cli): record nested-model description + schema link; refresh context"
```

---

## Self-Review

**1. Spec coverage:**
- Missing description → Tasks 1 (capture) + 2 (fall back). ✓
- Missing link → Tasks 3 (anchor slug) + 4 (template link + `<a id>`). ✓
- End-to-end proof + no strict-build regression → Task 5. ✓
- House-keeping (CHANGELOG, context, gate, live) → Task 6. ✓

**2. Placeholder scan:** every code/test step shows full code; commands have expected output. No TBD/TODO. ✓

**3. Type consistency:**
- `_model_doc(cls) -> str` (Task 1) consumed only inside `modelschema.py`.
- `ModelSchema.description: str` defined Task 1, read by `_model_desc` Task 2, populated registry-wide.
- `_model_desc(models, ref) -> str` (Task 2) used by both `_flag_row` and `_schema_rows`.
- `_anchor(key, flag_name) -> str` (Task 3) used by `_flag_row`; row key `type_anchor` consumed by the template (Task 4).
- `_flag_row(..., *, key="")` keyword threaded from `_command_view` (Task 3). ✓

## Residual risks / open items

- **Scope — nested type cells not linked.** Linking is applied to top-level Body/Arguments table rows only. A field *inside* a `??? note` disclosure whose type is another model (e.g. `contact` → `Contact`) renders as a plain `` `Contact` `` code span with no link — but that model's fields are shown directly below it via the existing `children` block, so the information is co-located. Deliberate (YAGNI); revisit only if users ask. **Open decision for the user.**
- **Anchor rendering (empirically verified by review).** `<a id="..."></a>` renders through python-markdown + `pymdownx.details` as `<p><a id="..."></a></p>` — id intact, admonition NOT swallowed, link resolves — **without** `md_in_html`. The blank line between the anchor and `??? note` is the load-bearing invariant (guarded by the Task-4 test asserting `lines[a+1] == ""` and the macro comment).
- **`--strict` does NOT validate intra-page fragments by default** (mkdocs 1.6 `validation.anchors` defaults to `info`). So the guard against link↔anchor drift is the Task-4 test asserting the Type-cell link slug is a subset of the emitted `<a id>` slugs — NOT the strict build. (Separately, mkdocs unions raw-HTML `<a id>` ids into `present_anchor_ids`, so even an escalated `validation.anchors: error` would resolve these links.)
- **Recursive description fallback.** The fallback fires at every nesting depth (`_schema_rows`), not just top-level body flags. Intended; documented in Task 2.
- **Slug `-`/`_` collapse.** `_anchor` maps both `-` and `_` runs to `-`, so `--app-group` and `--app_group` would collide. CLI flag names are kebab-case in practice, so this is not reachable; left as-is, documented here.
- **`desc == cls.__name__` false-negative.** A genuine model description that happens to equal the class name is dropped. Accepted: it matches openapi-generator's "class-name docstring == no description" convention, and the alternative (rendering the bare class name) is worse.
- **Multi-paragraph flattening.** `_model_doc` collapses a multi-paragraph component description to one line — intentional, since it only ever lands in a single GFM table cell.

## Open design decision (for user sign-off)

**Anchor mechanism — raw `<a id>` (planned default) vs heading-anchored disclosure.** The plan uses an invisible raw-HTML `<a id>`. The alternative is to precede each disclosure with a real heading carrying an `attr_list` id (`#### \`--profile\` schema {#create-widget-profile-schema}`), which is pure markdown, TOC-visible/deep-linkable, and natively `--strict`-validated. The trade-off: because the same flag repeats across several commands on one page, the heading variant adds N near-duplicate entries to that page's right-hand TOC (e.g. five "`--profile` schema" entries on the widget page). The raw `<a id>` keeps the TOC clean at the cost of one raw-HTML line. **Recommended: keep the raw `<a id>`** (cleaner TOC; verified to build). Switch to headings only if deep-linkability outweighs TOC clutter.
