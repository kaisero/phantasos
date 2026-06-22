# SDK Resource Docs — Body Detail (Tier 0 + Tier 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated-SDK resource reference docs teach users how to build a request body — by (Tier 0) rendering the already-typed wrapper signatures with clickable model cross-references, and (Tier 1) injecting a synthesized, copy-pasteable call example under each operation.

**Architecture:** Two independent changes to the SDK generator. **Tier 0** adds three `mkdocstrings` option keys to the scaffold's `mkdocs.yml.jinja` (config only — no codegen). **Tier 1** extends the wrapper render-prep in `src/phantasos/generator/sdk/wrapper.py` so each emitted `*Resource` method docstring carries an `**Example:**` block, reusing the existing `synthesize_body()` synthesizer. Examples are emitted only when docs are enabled; the example for the configured *showcase* resource honors the existing `docs.examples` overrides and `docs.showcase_variant`.

**Tech Stack:** Python 3.12+, Jinja2 templates, pydantic v2 (live model introspection), MkDocs + `mkdocstrings[python]` + `griffe-pydantic` (the emitted docs site), `nox` + `pytest` + `ruff` + `mypy` (the generator's gate).

## Global Constraints

- **Python floor:** 3.12+ (generator source and emitted SDKs).
- **Frozen oracles — never edit:** any path matching `protected_globs` in `.claude/harness.toml` (`products/*/overrides/tests/test_sdk_crud_live.py*`, `tests/acceptance/**`, `.claude/harness.toml`, `.claude/hooks/**`, `.claude/settings.json`). If one looks wrong, STOP and surface it.
- **Test policy:** prefer real dependencies; NEVER mock the system under test. Show real command output before claiming a pass (evidence before assertions).
- **The emitted SDK/CLI is disposable** — never hand-edit generated output; only `src/phantasos/**` and `products/<name>/**` are version-controlled customization surfaces.
- **Branching:** this is feature work — branch off `develop`, PR back into `develop` with `--base develop`, **squash-merge**, **no version bump**, record changes under `## [Unreleased]` in `CHANGELOG.md`.
- **sshfs venv:** run uv with an explicit env dir, e.g. `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run ...`. For venv-backed nox sessions also set `NOX_ENVDIR=/tmp/phantasos-nox`.
- **Context docs:** after changing the SDK-generator subsystem, update its deep-dive narrative (`.agents/context/sdk-generator.md` and/or `components.md`) and run `uv run nox -s context` (the `-- --check` block must pass).
- **Gate command:** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run nox -s gate` (ruff check, ruff format --check, mypy, pytest). Run before declaring any task complete.

---

## Design Decisions (from grilling, 2026-06-21)

These are settled. Do not re-litigate during implementation.

- **D1 — Tier 1 route = docstring injection (Route 1).** The example lands in each wrapper method's docstring in `resources.py`; mkdocstrings renders it, and it also appears in runtime `help()`. (Rejected: a docs-only sidecar consumed by `gen_ref_pages.py`.)
- **D2 — Empty all-optional bodies show the nav line + an optionality hint (not suppressed).** Synthesize the body; if it comes out an empty constructor (`PatchX()` / `PatchX(\n)`, i.e. a plain all-optional PATCH), still emit the call showing the client path + required path args + `body=PatchX()  # all fields optional`. The displayed type is whatever `synthesize_body` actually constructed (the model itself, or a chosen oneOf variant), so the body is always a valid empty construction. A oneOf PATCH whose variant has a *required discriminator* (e.g. showcase `application.update` → `CustomPatchApplicationInput(type="custom")`) is non-empty and shows that body verbatim. **(Updated per your call:** earlier this empty case was suppressed entirely; now it keeps the navigation line so `update` is consistent with every other verb.)
- **D3 — Example scope = every classified CRUD op.** Every op gets a block, because the block's unique value is the **client navigation path** (`client.<attr>.<verb>`), which the bare signature never shows: synthesized body example for create-style ops; `client.<attr>.get(id="<id>")` / `delete(...)` for path-param ops; `client.<attr>.list()` for list; and `client.<attr>.update(id="<id>", body=PatchX()  # all fields optional)` for all-optional updates (per D2).
- **D4 — Showcase resource honors `docs.showcase_variant`.** On the showcase resource's reference page, oneOf bodies use the configured variant so its reference example matches its guide example. All other resources default to the first variant.
- **D5 — Always-on when docs are enabled.** No new config flag. Tier 0 and Tier 1 apply whenever the product has docs (`loaded.config.docs is not None`); when docs are off, docstrings stay one-line (current behavior).
- **D6 — `docs.examples` overrides reach the showcase reference page.** For the showcase resource, an authored `docs.examples.<slot>` verbatim snippet is used on the reference page (matching the guide). An override is *real* (not synthesized), so it is shown **even for `update`** — D2 only suppresses *synthesized* empty bodies. All non-showcase resources are purely synthesized (per-resource overrides are Tier 2 roadmap).
- **D7 — Tests are behavioral on emitted artifacts.** Assert emitted `mkdocs.yml` / `resources.py` content; do NOT add a `mkdocs build` to the generator gate. Render/`--strict` correctness is verified once during implementation and covered ongoing by the emitted SDK's own `docs.yml` CI.

---

## Expert Review Outcomes (2026-06-21)

Three independent reviewers red-teamed this plan against the real code. Verdicts: **architecture/seams = GO-WITH-FIXES**, **tests/decisions = GO-WITH-FIXES**, **docs-rendering/`--strict` = GO**. All blocking findings are folded into the tasks above:

- **`--strict` reproduced GREEN** on a real SDK copy with both tiers applied — the only headline risk is retired (Task 5, Step 1).
- **No circular imports**; docs config reaches the real build path; empty-ctor suppression verified correct; all import paths valid; frozen oracles clear.
- Fixed: the `get` test assertion's off-by-indent (now substring-based, Task 3); the vacuous variant test (now uses a non-default variant, Task 4); the `api_cls = ...` sketch hole (body model now passed in, Task 3c); a latent enum-escaping landmine the plan widened (Task 2, Step 3b); D2/D3 narrative precision for discriminated PATCH bodies.

### Flagged decision — RESOLVED

The reviewers flagged that a plain all-optional `update` would show no navigation line. **Decision: close the gap** — D2/D3 are updated so every op (including all-optional `update`) emits its `client.<attr>.<verb>(...)` block; an all-optional body renders as `body=PatchX()  # all fields optional`. No suppression remains.

---

## Background (why each seam exists)

- **The reference page is autodoc.** `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` writes one `::: <pkg>.extras.resources.<Class>` directive per wrapper resource (plus one per `models/` module). mkdocstrings/griffe introspects the live class to render headings, signatures, and docstrings. No prose is generated — so to add a per-operation example we change what the **docstring** contains (Tier 1) and how mkdocstrings **renders signatures** (Tier 0).
- **The wrapper docstring seam.** `resources.py` is rendered from `src/phantasos/generator/sdk/components/facade/resource.py.jinja`; the method docstring is `"""{{ m.docstring }}"""` (line 31). `m.docstring` is a plain string set in `wrapper.py::_build_method` via `_method_docstring(...)`. If that string contains newlines (with continuation lines pre-indented to 8 spaces), the template renders a valid multi-line docstring with **no template change** — griffe's docstring cleaner dedents it.
- **The synthesizer already exists.** `src/phantasos/generator/sdk/examples.py::synthesize_body(model, *, variant=None)` returns a required-only constructor expression for a live pydantic model (enums → first value, `str→"example"`, nested models recurse, oneOf wrappers pick a variant). It is already used by `docs.py` for the one showcase resource.
- **Docs config is reachable at wrapper-render time.** `render.py::_vendor_resources` (around line 187) calls `build_wrapper_context(inv, loaded.config.operations, _discover_resources(pkg_dir))` and has `loaded` in scope — so `loaded.config.docs` (a `DocsConfig | None` with `showcase_resource: str`, `showcase_variant: str | None`, `examples: DocsExamples | None`) can be threaded in.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/phantasos/scaffold/mkdocs.yml.jinja` | Modify (mkdocstrings `options:` block, ~line 78) | **Tier 0**: enable typed signatures + cross-refs. |
| `src/phantasos/generator/sdk/examples.py` | Modify (add pure functions) | **Tier 1 core**: build the `**Example:**` block for one op (`reference_example`) and assemble the multi-line docstring (`assemble_reference_docstring`). |
| `src/phantasos/generator/sdk/wrapper.py` | Modify (`_build_method`, `build_wrapper_context`) | **Tier 1 wiring**: thread docs config; compute example inputs from live types; set `MethodView.docstring`. |
| `src/phantasos/generator/sdk/render.py` | Modify (`_vendor_resources` → pass `loaded.config.docs`) | Wire the docs config from `render` into `build_wrapper_context`. |
| `tests/test_sdk_docs_emitted.py` | Modify (extend mkdocs test) | Tier 0 assertion. |
| `tests/test_sdk_docs_examples.py` | Modify (add `reference_example` / `assemble_reference_docstring` tests) | Tier 1 core unit tests. |
| `tests/test_sdk_wrapper.py` | Modify (add emitted-docstring assertions) | Tier 1 wiring tests (real built SDK). |
| `.agents/context/sdk-generator.md` (and/or `components.md`) | Modify (narrative) | Document the new behavior; refresh generated blocks via `nox -s context`. |

---

### Task 1: Tier 0 — typed signatures + clickable model cross-refs

Config-only. Independently shippable.

**Files:**
- Modify: `src/phantasos/scaffold/mkdocs.yml.jinja` (mkdocstrings `options:` block; insert after `members_order: source`, ~line 78)
- Test: `tests/test_sdk_docs_emitted.py` (extend `test_mkdocs_enables_griffe_pydantic_and_filters`, ~line 207)

**Interfaces:**
- Consumes: nothing.
- Produces: an emitted `mkdocs.yml` whose `mkdocstrings` options include `show_signature_annotations: true`, `separate_signature: true`, `signature_crossrefs: true`.

- [ ] **Step 1: Write the failing assertion** — append to `test_mkdocs_enables_griffe_pydantic_and_filters` in `tests/test_sdk_docs_emitted.py`:

```python
    # Tier 0: render the body model type in the signature, as a clickable
    # cross-reference to its own reference page (turns `create(body=None)` into
    # `create(body: CreateXRequest | None = None)` with CreateXRequest linked).
    for key in (
        "show_signature_annotations: true",
        "separate_signature: true",
        "signature_crossrefs: true",
    ):
        assert key in mk, key
```

- [ ] **Step 2: Run it and verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_docs_emitted.py::test_mkdocs_enables_griffe_pydantic_and_filters -v`
Expected: FAIL — `assert 'show_signature_annotations: true' in mk`.

- [ ] **Step 3: Add the three keys** to `src/phantasos/scaffold/mkdocs.yml.jinja`. Change:

```jinja
            show_root_heading: true
            show_docstring_parameters: false
            members_order: source
```

to:

```jinja
            show_root_heading: true
            show_docstring_parameters: false
            members_order: source
            # Render the typed signature as a separate, cross-linked code block
            # so each param's model type links to its own reference page.
            show_signature_annotations: true
            separate_signature: true
            signature_crossrefs: true
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_docs_emitted.py::test_mkdocs_enables_griffe_pydantic_and_filters -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/scaffold/mkdocs.yml.jinja tests/test_sdk_docs_emitted.py
git commit -m "feat(sdk-docs): render typed wrapper signatures with model cross-refs (Tier 0)"
```

---

### Task 2: Tier 1 core — `reference_example` + `assemble_reference_docstring`

Pure functions, no SDK build required. This is the heart of Tier 1 and is fully unit-testable with hand-built pydantic models.

**Files:**
- Modify: `src/phantasos/generator/sdk/examples.py` (add functions + private helpers at end of file)
- Test: `tests/test_sdk_docs_examples.py` (add tests)

**Interfaces:**
- Consumes: `synthesize_body(model, *, variant=None) -> str` (already in this module).
- Produces (relied on by Task 3):
  - `reference_example(*, attr: str, method: str, path_args: list[tuple[str, str]], body_model: type[BaseModel] | None, variant: str | None = None, override: str | None = None) -> str | None`
  - `assemble_reference_docstring(summary: str, example: str | None) -> str`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_sdk_docs_examples.py` (reuse the existing `CustomApp`/`UrlInput`/`Color` models in that file; add two all-optional models):

```python
from phantasos.generator.sdk.examples import (
    assemble_reference_docstring,
    reference_example,
)


class AllOptional(BaseModel):  # mirrors a PATCH body: nothing required
    name: str | None = None
    note: str | None = None


def test_reference_example_create_includes_body_and_client_path() -> None:
    ex = reference_example(
        attr="custom_app",
        method="create",
        path_args=[],
        body_model=CustomApp,
    )
    assert ex is not None
    assert ex.startswith("**Example:**\n\n```python\n")
    assert "client.custom_app.create(" in ex
    assert "body=CustomApp(" in ex
    assert ex.rstrip().endswith("```")


def test_reference_example_path_only_op_shows_client_call() -> None:
    ex = reference_example(
        attr="custom_app", method="get",
        path_args=[("id", "<id>")], body_model=None,
    )
    assert ex == '**Example:**\n\n```python\nclient.custom_app.get(\n    id="<id>",\n)\n```'


def test_reference_example_list_no_args() -> None:
    ex = reference_example(
        attr="custom_app", method="list", path_args=[], body_model=None,
    )
    assert ex == "**Example:**\n\n```python\nclient.custom_app.list()\n```"


def test_reference_example_all_optional_body_shows_nav_line_with_hint() -> None:
    # D2 (updated): an empty all-optional body is NOT suppressed — show the nav
    # line + an empty, valid body + an optionality hint.
    ex = reference_example(
        attr="custom_app", method="update",
        path_args=[("id", "<id>")], body_model=AllOptional,
    )
    assert ex is not None
    assert "client.custom_app.update(" in ex
    assert 'id="<id>"' in ex
    assert "body=AllOptional()" in ex
    assert "# all fields optional" in ex
    # the empty body must be valid Python (strip the markdown fence, then parse)
    import ast
    code = ex.split("```python\n", 1)[1].rsplit("\n```", 1)[0]
    ast.parse(code)


def test_reference_example_override_is_used_verbatim() -> None:
    # D6: an authored override is shown even when the synthesized body would be empty.
    ex = reference_example(
        attr="custom_app", method="update", path_args=[("id", "<id>")],
        body_model=AllOptional,
        override="updated = client.custom_app.update(id=\"abc\", body=AllOptional(name=\"x\"))",
    )
    assert ex == (
        "**Example:**\n\n```python\n"
        'updated = client.custom_app.update(id="abc", body=AllOptional(name="x"))\n'
        "```"
    )


def test_assemble_docstring_single_line_when_no_example() -> None:
    assert assemble_reference_docstring("Delete a thing.", None) == "Delete a thing."


def test_assemble_docstring_indents_continuation_to_eight_spaces() -> None:
    doc = assemble_reference_docstring(
        "Create a thing.",
        "**Example:**\n\n```python\nclient.x.create()\n```",
    )
    lines = doc.split("\n")
    assert lines[0] == "Create a thing."          # summary stays flush (after the opening quotes)
    assert lines[1] == ""                          # blank lines are not indented
    assert lines[2] == "        **Example:**"      # continuation indented 8 spaces
    assert "        client.x.create()" in lines
```

- [ ] **Step 2: Run them and verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_docs_examples.py -k "reference_example or assemble_docstring" -v`
Expected: FAIL — `ImportError: cannot import name 'reference_example'`.

- [ ] **Step 3: Implement the functions** — append to `src/phantasos/generator/sdk/examples.py`:

```python
import re

# `Name()` / `Name(\n)` — an empty constructor: a plain all-optional PATCH body.
# These are NOT suppressed; they render as `body=Name()  # all fields optional`.
# A discriminated PATCH renders `Name(\n    type="x",\n)` (non-empty) and is not
# matched — it shows its body verbatim.
_EMPTY_CTOR = re.compile(r"^\w+\(\s*\)\Z")
_DOC_INDENT = " " * 8  # method-body docstring indentation


def _example_block(code: str) -> str:
    """Wrap a code snippet as the Markdown example block griffe renders."""
    return f"**Example:**\n\n```python\n{code}\n```"


def reference_example(
    *,
    attr: str,
    method: str,
    path_args: list[tuple[str, str]],
    body_model: type[BaseModel] | None,
    variant: str | None = None,
    override: str | None = None,
) -> str | None:
    """The `**Example:**` block for one wrapper op (always returns a block here).

    - `override` (showcase only) is used verbatim — author-written, not
      synthesized — so it wins even for an all-optional body (D6).
    - An empty synthesized body (a plain all-optional PATCH) is NOT suppressed:
      it renders as `body=Name()  # all fields optional` so the client path +
      model are visible and the user fills the fields (D2).
    - The call always shows the client navigation path `client.<attr>.<method>`
      plus required path args; the body kwarg is appended when present (D3).

    (`None` is reserved for future "truly nothing to show" cases; with current
    policy every op yields a block.)
    """
    if override is not None:
        return _example_block(override.strip())
    body_code: str | None = None
    body_comment = ""
    if body_model is not None:
        synthesized = synthesize_body(body_model, variant=variant)
        if _EMPTY_CTOR.match(synthesized):
            # All-optional body: show the actually-constructed type (the model, or
            # a chosen oneOf variant) as an empty, valid call + an optionality hint.
            ctor = synthesized.split("(", 1)[0]
            body_code = f"{ctor}()"
            body_comment = "  # all fields optional"
        else:
            body_code = synthesized
    lines = [f"client.{attr}.{method}("]
    for name, placeholder in path_args:
        lines.append(f'    {name}="{placeholder}",')
    if body_code is not None:
        lines.append(f"    body={_continuation_indent(body_code, _INDENT)},{body_comment}")
    code = (
        f"client.{attr}.{method}()"
        if len(lines) == 1
        else "\n".join(lines) + "\n)"
    )
    return _example_block(code)


def assemble_reference_docstring(summary: str, example: str | None) -> str:
    """Combine the one-line summary with an example block into a docstring body.

    The summary stays flush (it follows the opening triple-quote); every
    non-blank continuation line is indented to the method-body level so the
    emitted `\"\"\"{{ m.docstring }}\"\"\"` is valid Python. griffe's docstring
    cleaner dedents it before rendering.
    """
    if example is None:
        return summary
    body = f"{summary}\n\n{example}"
    head, _, tail = body.partition("\n")
    cont = "\n".join(_DOC_INDENT + ln if ln else "" for ln in tail.split("\n"))
    return f"{head}\n{cont}"
```

Note: `_continuation_indent` and `_INDENT` already exist in this module (used by `synthesize_body`); reuse them so the body kwarg aligns under `body=`.

- [ ] **Step 3b: Harden `_enum_literal` against unescaped values.** Review flagged that `_enum_literal` currently builds `f'"{first}"'` — an enum first-value containing a `"`, backslash, or newline would emit broken Python. This is pre-existing, but Tier 1 extends `synthesize_body` from one showcase resource to *every* resource docstring, widening the blast radius (a broken literal would fail the whole product's smoke build). Change the string-enum branch in `_enum_literal` (`examples.py`) from `return f'"{first}"'` to `return json.dumps(first)` (add `import json` at top), so quotes/backslashes are escaped. Add a unit test to `tests/test_sdk_docs_examples.py`:

```python
def test_enum_first_value_with_quote_is_escaped() -> None:
    class Tricky(str, enum.Enum):  # noqa: UP042
        FANCY = 'say "hi"'

    class Body(BaseModel):
        kind: Tricky

    out = synthesize_body(Body)
    # must be valid Python — the quote is escaped, not raw
    import ast
    ast.parse(out)
    assert r'"say \"hi\""' in out or "'say \"hi\"'" in out
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_docs_examples.py -v` (runs the new `reference_example`/`assemble_docstring`/enum tests plus the existing `synthesize_body` suite)
Expected: PASS (all green — the 7 new functional tests + the enum-escaping test + the pre-existing ones).

- [ ] **Step 5: Run ruff + mypy on the touched module**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run ruff check src/phantasos/generator/sdk/examples.py && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run mypy src/phantasos/generator/sdk/examples.py`
Expected: clean. (Move the `import re` to the top-of-file import block if ruff flags `E402`.)

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/sdk/examples.py tests/test_sdk_docs_examples.py
git commit -m "feat(sdk-docs): synthesize per-op reference examples (Tier 1 core)"
```

---

### Task 3: Tier 1 wiring — emit examples into wrapper docstrings

Thread the docs config to the docstring builder and use the live body type already resolved in `_build_method`.

**Files:**
- Modify: `src/phantasos/generator/sdk/wrapper.py` (`build_wrapper_context`, `_build_method`)
- Modify: `src/phantasos/generator/sdk/render.py` (`_vendor_resources` call site, ~line 187)
- Test: `tests/test_sdk_wrapper.py` (add emitted-docstring assertions against the real built SDK)

**Interfaces:**
- Consumes: `reference_example`, `assemble_reference_docstring` (Task 2); `DocsConfig` from `phantasos.productconfig` (`showcase_resource: str`, `showcase_variant: str | None`, `examples: DocsExamples | None`).
- Produces: `build_wrapper_context(inv, overrides, discovered, *, docs: DocsConfig | None = None)` — when `docs` is not None, every `MethodView.docstring` is a multi-line docstring with an `**Example:**` block (where informative).

- [ ] **Step 1: Write the failing test** — add to `tests/test_sdk_wrapper.py`. This builds the real wrapper context against the sibling `prisma-browser-sdk` and asserts emitted docstrings. Follow the existing module's pattern for locating the SDK and calling `build_wrapper_context`/`introspect`; the assertions are:

```python
def test_reference_examples_emitted_into_docstrings() -> None:
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.productconfig import DocsConfig

    sdk = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
    inv = introspect("prisma_browser", sdk)
    docs = DocsConfig(showcase_resource="application")
    objects = build_wrapper_context(inv, {}, _discover(sdk), docs=docs)

    rule = next(o for o in objects if o.classname == "AccessAndDataRuleResource")
    create = next(m for m in rule.methods if m.name == "create")
    update = next(m for m in rule.methods if m.name == "update")
    get = next(m for m in rule.methods if m.name == "get")

    # create-style body -> synthesized example with the client path + body model
    assert "**Example:**" in create.docstring
    assert "client.access_and_data_rule.create(" in create.docstring
    assert "body=CreateAccessAndDataRuleRequest(" in create.docstring
    # path-only op -> client-path call with required id. Assert on substrings,
    # NOT an exact multi-line literal: `assemble_reference_docstring` re-indents
    # every continuation line by 8 spaces (so the call sits at 8, `id=` at 12),
    # and that indentation is an implementation detail of the assembler.
    assert "client.access_and_data_rule.get(" in get.docstring
    assert 'id="<id>"' in get.docstring
    # plain all-optional PATCH body -> nav line + empty body + optionality hint (D2)
    assert "**Example:**" in update.docstring
    assert "client.access_and_data_rule.update(" in update.docstring
    assert "# all fields optional" in update.docstring


def test_no_examples_when_docs_disabled() -> None:
    # D5 inverse: docs=None -> one-line docstrings, no example block leaks in.
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.generator.opmodel.introspect import introspect

    sdk = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
    inv = introspect("prisma_browser", sdk)
    objects = build_wrapper_context(inv, {}, _discover(sdk))  # no docs=
    for obj in objects:
        for m in obj.methods:
            assert "**Example:**" not in m.docstring
            assert "\n" not in m.docstring  # stays one line
```

`_discover` is a small test helper. Note: `test_sdk_wrapper.py` today imports `_discover_resources` at module scope and calls `_discover_resources(PKG)` directly — there is no `_discover` wrapper yet, so add this one (it just adapts the SDK-root path to the package dir `_discover_resources` expects):

```python
def _discover(sdk: Path) -> list[dict[str, str]]:
    from phantasos.generator.sdk.render import _discover_resources
    return _discover_resources(sdk / "prisma_browser")
```

- [ ] **Step 2: Run it and verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_wrapper.py::test_reference_examples_emitted_into_docstrings -v`
Expected: FAIL — `build_wrapper_context() got an unexpected keyword argument 'docs'` (or `**Example:** not in create.docstring`).

- [ ] **Step 3a: Thread `docs` through `build_wrapper_context`.** In `src/phantasos/generator/sdk/wrapper.py`, change the signature:

```python
def build_wrapper_context(
    inv: OperationInventory,
    overrides: dict[str, OperationOverride],
    discovered: list[dict[str, str]],
    *,
    docs: "DocsConfig | None" = None,
) -> list[ObjectView]:
```

Add the import under the existing `TYPE_CHECKING` block at the top of the file:

```python
if TYPE_CHECKING:
    from ...productconfig import DocsConfig
```

Pass `docs` and `obj_attr` into `_build_method` at the existing call site (the loop near line 699):

```python
        mv, imports = _build_method(
            method,
            obj_verb[(obj_attr, method)],
            ops,
            api_by_attr,
            api_attr_of,
            inv.sdk_package,
            obj_attr,
            docs=docs,
        )
```

- [ ] **Step 3b: Build the example in `_build_method`.** Add `docs` to its signature and replace the `docstring=_method_docstring(...)` argument of the `MethodView(...)` construction with a computed multi-line docstring. Add this `import` near the other local imports in `wrapper.py` (top of file is fine):

```python
from .examples import assemble_reference_docstring, reference_example
from .docs import _VERB_SLOT
from ..cli.introspect import _unwrap_optional
```

Change the signature:

```python
def _build_method(
    method: str,
    verb: str,
    ops: list[OperationInfo],
    api_by_attr: dict[str, type[Any]],
    api_attr_of: dict[str, str],
    package: str,
    obj_attr: str = "",
    *,
    docs: "DocsConfig | None" = None,
) -> tuple[MethodView, set[tuple[str, str]]]:
```

`_build_method` already resolves the live body type inside its `for op in ops:` loop. In the existing body branch (`if op_param.location == "body":`, ~line 473-481), capture the unwrapped body class into a local initialized to `None` before the loop:

```python
    body_model_live: type[Any] | None = None
    # ... inside the loop's body branch, alongside the existing `pv = _param_view("body", ...)`:
            if body_model_live is None:
                _unwrapped = _unwrap_optional(live_type)
                body_model_live = _unwrapped if isinstance(_unwrapped, type) else None
```

This reuses the body type the method already exposes (so the example's body and the signature's `body:` annotation can never disagree — addresses the multi-binding concern). Then, just before the `mv = MethodView(...)` construction, compute the docstring:

```python
    summary = _method_docstring(method, obj_attr, ops)
    docstring = summary
    if docs is not None:
        example = _reference_example_for(method, obj_attr, ops, body_model_live, docs)
        docstring = assemble_reference_docstring(summary, example)
```

and set `docstring=docstring` in the `MethodView(...)` kwargs (replacing `docstring=_method_docstring(method, obj_attr, ops)`).

- [ ] **Step 3c: Add the `_reference_example_for` helper** to `wrapper.py` (it owns the "what to pass to `reference_example`" policy — minimal-call path placeholders + showcase override/variant per D4/D6; the body model is passed in from Step 3b, NOT re-resolved):

```python
def _reference_example_for(
    method: str,
    obj_attr: str,
    ops: list[OperationInfo],
    body_model: type[Any] | None,
    docs: "DocsConfig",
) -> str | None:
    """Compute the reference-example block for one wrapper method, or None."""
    # Illustrate the binding with the fewest required path params (the minimal call).
    example_op = min(ops, key=_req_path_param_count)
    path_args: list[tuple[str, str]] = [
        (p.name, p.enum_values[0] if p.enum_values else f"<{p.name}>")
        for p in example_op.params
        if p.location == "path" and p.required
    ]
    # Showcase: honor the configured variant + per-slot verbatim override (D4/D6).
    is_showcase = obj_attr == docs.showcase_resource
    variant = docs.showcase_variant if is_showcase else None
    override = None
    if is_showcase and docs.examples is not None:
        slot = _VERB_SLOT.get(method)
        if slot is not None:
            override = getattr(docs.examples, slot, None)
    return reference_example(
        attr=obj_attr,
        method=method,
        path_args=path_args,
        body_model=body_model,
        variant=variant,
        override=override,
    )


def _req_path_param_count(op: OperationInfo) -> int:
    """Count required PATH params (distinct from the existing `_required_path_params`,
    which returns the tuple of names — this returns the count for `min(...)` keying)."""
    return sum(1 for p in op.params if p.location == "path" and p.required)
```

**No circular-import risk (verified in review):** `examples.py` and `docs.py` do not import `wrapper.py` (the only importer of `wrapper.py` is `render.py`, lazily). The `from .docs import _VERB_SLOT` and `from .examples import ...` lines at the top of `wrapper.py` are safe.

- [ ] **Step 3d: Pass the docs config from `render.py`.** In `src/phantasos/generator/sdk/render.py`, at the `build_wrapper_context(...)` call inside `_vendor_resources` (~line 187):

```python
        objects = build_wrapper_context(
            inv,
            loaded.config.operations,
            _discover_resources(pkg_dir),
            docs=loaded.config.docs,
        )
```

- [ ] **Step 4: Run the wiring test and verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_wrapper.py::test_reference_examples_emitted_into_docstrings -v`
Expected: PASS.

- [ ] **Step 5: Run the full wrapper + docs test modules + ruff/mypy**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_wrapper.py tests/test_render.py tests/test_sdk_docs_examples.py -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run ruff check src/phantasos/generator/sdk/ && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run mypy src/phantasos/generator/sdk/`
Expected: PASS / clean. Review confirmed `test_render.py::test_resources_emitted` does **not** break — its assertion is a prefix check (`'"""Get a' in src or ...`) that still matches the flush summary as docstring line 1, so no edit there is needed. (Should any other test assert an exact one-line docstring, update it to the multi-line form — all four touched test files are ordinary, NOT frozen oracles, confirmed against `protected_globs`.)

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/sdk/wrapper.py src/phantasos/generator/sdk/render.py tests/test_sdk_wrapper.py tests/test_render.py
git commit -m "feat(sdk-docs): emit per-op reference examples into wrapper docstrings (Tier 1)"
```

---

### Task 4: Showcase variant + override on the reference page (D4/D6)

The `reference_example` machinery already accepts `variant`/`override` and Task 3 wires them for the showcase. This task adds the *targeted* tests that lock D4/D6 so a future refactor can't silently drop them.

**Files:**
- Test: `tests/test_sdk_wrapper.py` (add two tests)

**Interfaces:**
- Consumes: `build_wrapper_context(..., docs=DocsConfig(...))` from Task 3.
- Produces: nothing new (verification only).

- [ ] **Step 1: Write the failing tests** — add to `tests/test_sdk_wrapper.py`:

```python
def test_showcase_reference_honors_variant() -> None:
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.productconfig import DocsConfig

    sdk = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
    inv = introspect("prisma_browser", sdk)
    # application.create has a oneOf body. Use a NON-default variant so the test
    # actually proves variant threading: `CustomApplicationInput` is the FIRST
    # (default) variant, so asserting it would pass even if the variant arg were
    # dropped. `PrivateApplicationInput` is only emitted when the variant is honored.
    docs = DocsConfig(showcase_resource="application", showcase_variant="PrivateApplicationInput")
    objects = build_wrapper_context(inv, {}, _discover(sdk), docs=docs)
    app = next(o for o in objects if o.classname == "ApplicationResource")
    create = next(m for m in app.methods if m.name == "create")
    assert "PrivateApplicationInput(" in create.docstring
    assert "CustomApplicationInput(" not in create.docstring  # default did NOT win


def test_discriminated_patch_update_still_shows_example() -> None:
    # Refined D2/D3: an all-optional PATCH is suppressed, BUT a oneOf PATCH whose
    # variant has a required discriminator synthesizes a NON-empty body, so it is
    # NOT suppressed. `application.update` (oneOf PatchAppInput) is the real case.
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.productconfig import DocsConfig

    sdk = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
    inv = introspect("prisma_browser", sdk)
    objects = build_wrapper_context(
        inv, {}, _discover(sdk), docs=DocsConfig(showcase_resource="application")
    )
    app = next(o for o in objects if o.classname == "ApplicationResource")
    update = next(m for m in app.methods if m.name == "update")
    assert "**Example:**" in update.docstring          # NOT suppressed
    assert "client.application.update(" in update.docstring
    assert "body=" in update.docstring                 # carries the discriminated variant


def test_showcase_override_used_verbatim_even_for_update() -> None:
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.productconfig import DocsConfig, DocsExamples

    sdk = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
    inv = introspect("prisma_browser", sdk)
    docs = DocsConfig(
        showcase_resource="access_and_data_rule",
        examples=DocsExamples(update="updated = client.access_and_data_rule.update(id=\"abc\")"),
    )
    objects = build_wrapper_context(inv, {}, _discover(sdk), docs=docs)
    rule = next(o for o in objects if o.classname == "AccessAndDataRuleResource")
    update = next(m for m in rule.methods if m.name == "update")
    # D6: an authored override is shown even though synthesized update bodies are suppressed.
    assert "**Example:**" in update.docstring
    assert 'updated = client.access_and_data_rule.update(id="abc")' in update.docstring
```

- [ ] **Step 2: Run them**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run pytest tests/test_sdk_wrapper.py -k "showcase or discriminated" -v`
Expected: PASS, all three (Task 3 already implements the behavior). If any fails, fix the showcase branch in `_reference_example_for` until green — do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sdk_wrapper.py
git commit -m "test(sdk-docs): lock showcase variant + override on reference pages (D4/D6)"
```

---

### Task 5: Render verification, context docs, and roadmap

Behavioral tests prove emitted *content*; this task proves the page actually *renders* and updates the durable docs.

**Files:**
- Modify: `.agents/context/sdk-generator.md` (narrative) and/or `.agents/context/components.md`
- (This plan doc already holds the Tier 2 roadmap — see below.)

- [ ] **Step 1: Rebuild the prisma-browser SDK** (real generator end-to-end), then build its docs with `--strict`:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan uv run phantasos sdk build prisma-browser
cd <prisma-browser-sdk output dir>
UV_PROJECT_ENVIRONMENT=/tmp/pbsdk-docs uv run --group docs mkdocs build --strict
```

Expected: build exits 0 with no warnings (mkdocs `--strict` fails on any warning). **Review already reproduced this green** (Tier 0 + Tier 1 injected into a copy of the built SDK → `mkdocs build --strict` exited 0, no griffe/mkdocstrings warnings about code blocks, sections, or `**Example:**`). So the `_hooks.py.jinja` matcher is a **contingency, not an expected step**: only if a warning *does* appear, add a matcher to that hook (the existing seam that filters benign "Duplicate parameter information" warnings).

- [ ] **Step 1b (optional polish): add `ruff` to the emitted `docs` group.** With `separate_signature: true`, mkdocstrings logs an INFO and renders signatures unformatted unless `black` or `ruff` is importable in the docs env. Adding `ruff` to the `docs` dependency-group in `src/phantasos/scaffold/pyproject.toml.jinja` yields nicely wrapped multi-line signatures. Not required (`--strict` passes without it); skip if you want to avoid touching the dependency set.

- [ ] **Step 2: Spot-check the rendered page** — confirm `reference/resources/access_and_data_rule/index.html` shows: the typed `create(body: CreateAccessAndDataRuleRequest | None = ...)` signature with `CreateAccessAndDataRuleRequest` linked (Tier 0), and an `**Example:**` code block under **every** op — `create`/`get`/`delete`/`list`, plus `update` rendered as `client.access_and_data_rule.update(id="<id>", body=PatchAccessAndDataRuleByIDRequest()  # all fields optional)`. Also confirm `reference/resources/application/index.html` shows `update` with the discriminated variant body (`CustomPatchApplicationInput(type=...)`).

- [ ] **Step 3: Update the context deep-dive** — in `.agents/context/sdk-generator.md` (and `components.md` if the facade section lives there), add a short paragraph: the wrapper docstrings now carry per-op `**Example:**` blocks synthesized via `examples.reference_example`, gated on `docs` being enabled; the showcase resource honors `docs.showcase_variant`/`docs.examples`; all-optional bodies render `body=Model()  # all fields optional`; Tier 0 enables typed signatures + cross-refs in `mkdocs.yml`.

- [ ] **Step 4: Refresh generated context blocks**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s context && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s context -- --check`
Expected: clean / `--check` passes.

- [ ] **Step 5: Record the change in `CHANGELOG.md`** under `## [Unreleased]`:

```markdown
### Added
- Generated SDK reference docs now show typed wrapper signatures with clickable
  request-body model links, and a synthesized copy-pasteable example under every
  operation (all-optional update bodies render `body=Model()  # all fields optional`).
```

- [ ] **Step 6: Run the full gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-plan NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s gate`
Expected: PASS (ruff, format, mypy, pytest). Then run `uv run nox -s live` per the project test policy before declaring the work complete.

- [ ] **Step 7: Commit**

```bash
git add .agents/context CHANGELOG.md
git commit -m "docs(context): document per-op reference examples + Tier 0 signatures"
```

---

## Tier 2 Roadmap (out of scope; documented per request)

Priority-flagged follow-ups that close the *semantic-fidelity* ceiling. None are required for Tier 0/1 to land.

1. **[High] Per-resource / per-product `docs.examples` overrides.** Extend the override surface beyond the single showcase resource so authors can supply semantically-correct, copy-paste-runnable examples for any resource (key by `resource.slot`). The main lever for "the example actually works against the API."
2. **[High] Pattern/format-aware placeholder values.** Make synthesized scalar values satisfy `pattern`/`minLength`/`maxLength`/`format` (e.g. realistic IDs, emails, dates) so create examples pass server-side validation instead of just constructing.
3. **[Medium] Nested all-optional enrichment.** Fill the empty-nested case (`applications=AccessAndDataPostApplications()`), e.g. include a representative sub-field or honor `minProperties`, without bloating the top-level example.
4. **[Medium] Per-resource / per-slot oneOf variant selection.** Variant control beyond the showcase resource (today non-showcase resources always take the first variant). Note the per-slot gap surfaced in review: `docs.showcase_variant` is a single name that can only match one slot's variant family (e.g. a *create* variant `CustomApplicationInput`, not the *patch* variant `CustomPatchApplicationInput`), so a showcase `update` falls back to its first variant. Per-slot variant config would close this.
5. **[Medium] OpenAPI `examples:` harvesting.** Prefer spec-provided `examples:`/`example:` values over synthesized placeholders when specs eventually carry them (today this product has zero named `examples:`).
6. **[Low/reactive] Per-product Tier 1 opt-out flag.** Add `docs.reference_examples: false` only if a product ever needs terse runtime docstrings.

---

## Self-Review

- **Spec coverage:** Tier 0 → Task 1. Tier 1 core (synthesis, D2 empty-body nav-line + `# all fields optional` hint, D3 scope, enum-escaping hardening) → Task 2. Tier 1 wiring + always-on/D5 (incl. the `docs=None` inverse test) → Task 3. D4/D6 + the discriminated-PATCH refinement (showcase variant via non-default proof, verbatim override, `application.update` shows discriminator) → Tasks 3–4. Tests/D7 → Tasks 1–4. Render/`--strict` (reproduced green in review) + context docs → Task 5. Roadmap (all 6) → documented above.
- **Placeholder scan:** none. (The earlier `api_cls = ...` sketch hole in Task 3c was removed in review — the body model is now resolved in `_build_method` and passed into `_reference_example_for` as a parameter.)
- **Type consistency:** `reference_example(*, attr, method, path_args, body_model, variant, override) -> str | None` and `assemble_reference_docstring(summary, example) -> str` are defined in Task 2 and consumed with the same names/signatures in Task 3; `_reference_example_for(method, obj_attr, ops, body_model, docs) -> str | None` is defined and called consistently in Task 3; `build_wrapper_context(..., *, docs=None)` and `_build_method(..., *, docs=None)` are consistent across Tasks 3–4. `_VERB_SLOT` (imported from `docs.py`) maps `get→read` for override lookup, matching `DocsExamples` fields (`create/read/list/update/delete`). The empty/uninformative suppression constant is `_UNINFORMATIVE_BODY` (used in Task 2's `reference_example`).
