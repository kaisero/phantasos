# SDK reference docs: anyOf/oneOf wrapper rendering — Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with the
> subagent-driven-development flow (fresh implementer per task, two-stage review
> after each). Steps use checkbox (`- [ ]`) syntax. All implementers on Opus.

**Goal:** Make a generated SDK's reference page for an openapi-generator
anyOf/oneOf *wrapper* model show its real payload fields (with SCM container
boilerplate collapsed) instead of the wrapper scaffolding.

**Spec:** `docs/specs/2026-06-27-sdk-docs-oneof-wrapper-rendering.md` (rev 3 is
authoritative; it records the two python-pro reviews and the grilled decisions).

---

## Business intent — validate this before any code

**Who hurts today.** A developer using the generated `prisma_access` SDK opens the
reference page for a body model — say `AddressGroups`, the body of
`client.objects.address_group.create(...)` — to learn what to send. Instead of the
address-group fields, they see openapi-generator's internal scaffolding
(`anyof_schema_1_validator`, `anyof_schema_2_validator`, `actual_instance`,
`any_of_schemas`) and no path to the real shape. The same scaffolding leak hits **all
264** anyOf/oneOf wrapper model pages in `prisma_access` (of which the AddressGroups-
shaped payload+container bodies are ~10, and 14 are scalar-only), plus the quickstart's
`create` example (which renders an opaque `Addresses(...)`). prisma-browser's docs are
fine — its bodies are plain models — so this is specific to the SCM-style specs' heavy
anyOf/oneOf usage.

**What we want to achieve.** The model reference page should answer "what do I put in
the body?" directly:
- Show the **payload** fields inline — the address-group-specific shapes
  (`Static{static}`, `Dynamic{dynamic}`), grouped by their branch.
- **De-emphasize the container** — SCM's `folder`/`snippet`/`device` placement is
  boilerplate that repeats on every object; collapse it to one line so it doesn't
  drown the payload.
- Make the quickstart **example constructable** — a real payload-variant constructor,
  not an opaque placeholder.

**Why it matters.** The generated docs site is a primary deliverable of the SDK
generator. For the prisma-access product, unreadable model docs make the SDK hard to
adopt — the user can't discover the request shape without reading the OpenAPI spec by
hand, which defeats the point of generating an SDK. This is the difference between
"there are docs" and "the docs are usable for SCM."

**What this is NOT.** We are not reshaping the SDK models (the anyOf/oneOf wrapper
shape is openapi-generator's; flattening it at the model layer is a separate, much
larger problem). This is **docs-rendering only** — same models, better pages.

**Done looks like.**
1. The `AddressGroups` page shows `Static`/`Dynamic` payload fields inline, grouped,
   with `Placement: folder · snippet · device` as a one-liner — no `anyof_schema_*`
   scaffolding.
2. Every wrapper page (oneOf + anyOf, both products) renders consistently this way;
   plain-model pages are byte-identical to today.
3. The quickstart `create` example for the showcase resource constructs a real payload
   variant.
4. Wrapper bodies whose variants are primitives (`str`, `list[str]`) render those as
   code spans — never a blank page.

---

## Plan rev 2 — review corrections (READ FIRST; authoritative over the task steps below)

A python-pro review of rev 1 (validated against both built SDKs) found the rev-1
mechanism breaks the docs gate. These corrections govern; where they conflict with a
task step below, follow the correction.

- **C1 (Blocker) — Task B renders synthesized field TABLES, not `::: leaf` blocks.**
  Inlining `::: <leaf>` re-renders a model that already has its own page → duplicate
  primary autodoc anchors → `mkdocs build --strict` aborts (the exact gate
  `nox -s sdk-docs` runs). Instead, for each payload leaf hand-render a markdown table
  from `leaf.model_fields` — `| field | type | required |` — as plain markdown (no
  autodoc anchors, `--strict`-safe). The wrapper's own `::: <wrapper>` line stays (the
  Task-A global filter reduces it to its docstring). So a wrapper page = its docstring
  + per-payload-branch heading + field tables + the container one-liner + scalar code
  spans. Leaf standalone pages remain (no collision; duplication accepted). **Replace
  Task B step 5's `fd.write(f"::: {leaf_dotted}...")` loop with a `_field_table(leaf)`
  emitter.**
- **C2 (Blocker) — Task C must emit FULL nesting `AddressGroups(GroupType(Static(...)))`.**
  Verified: `AddressGroups(Static(...))` and `AddressGroups(actual_instance=Static(...))`
  both raise `ValidationError`; only the fully-nested wrapper-of-wrapper-of-leaf
  constructs. So `examples.py:_model_expr`'s wrapper branch must **wrap**, not unwrap:
  `return f"{model.__name__}({_continuation_indent(_model_expr(variant, seen), _INDENT)})"`
  (each wrapper layer wraps its child as one positional arg). The Task-C test must assert
  the full nesting / constructability (e.g. `"AddressGroups(GroupType(Static(" in out`),
  NOT merely `"Static(" in out` (which passes on the invalid bare form). **This also
  changes the existing browser oneOf example output** (`CustomApplicationInput(...)` →
  `CreateOrReplaceAppInput(CustomApplicationInput(...))`): update the assertions in
  `tests/test_sdk_docs_examples.py` (`test_oneof_*`, ~lines 83-88) and re-verify the
  showcase `body_code` expectations.
- **C3 (Important) — gate-resident tests must NOT import `prisma_access`.** `nox -s gate`
  builds prisma-browser/adem only; prisma-access is built solely in the opt-in
  `sdk-docs` session. So Task B/C unit tests that `import prisma_access...` ImportError
  under the gate. Use **synthetic in-test wrappers** for the gate-resident unit tests
  (a pydantic model with `actual_instance: Any` + `anyof_schema_1_validator:
  Optional[LeafLike]` fields, mirroring the OAG shape — see `tests/test_sdk_docs_examples.py`'s
  existing `_Wrapper`/`CustomApp` pattern). Put all real-`prisma_access` assertions in
  the `sdk-docs`/skipif-gated **rendered** test only.
- **C4 (Important) — the helper-exec mechanism is real work.** `gen_ref_pages.py.jinja`
  has no `__main__` guard and imports `mkdocs_gen_files` (not a phantasos dep), so
  "exec the rendered script and call its helpers" fails at module scope. Either (a)
  split the rendered text at a sentinel comment (`# --- helpers (no side effects) ---`)
  and exec only that region with a stubbed `mkdocs_gen_files`, or (b) move the driver
  body under `if __name__ ...`-style guard the script's runner respects. Pick (a) and
  state it in the test helper.
- **C5 (Important) — scalar variant labels come from `actual_instance`, not the
  validator fields.** The validator-field annotations are `Annotated[str, Strict(...)]`,
  so `_type_label` on them yields malformed `` `list[`Annotated`]` `` and loses
  `str`/`int`. The `actual_instance` annotation is clean (`ApplicationsRisk = int|str`,
  `ZonesNetwork = List[str] | object`). So: resolve **model** variants from the
  validator fields (robust, correct order — keep), but resolve **scalar** labels from
  `actual_instance`'s Union (clean), and make `_type_label` unwrap `Annotated` (via
  `get_args`) and avoid nested backticks. Add a mixed scalar+model wrapper test
  (browser `PatchUrls`/`PatchCidrs`).
- **C6 (Important) — a `--strict` rendered-build test PRECEDES/anchors Task B.** The
  duplicate-anchor failure is invisible to string/unit tests (rev 1 looked green while
  the gate would be red). Task B's first step is a test that builds the docs (or runs
  the gen script + `mkdocs build --strict` on a fixture) and asserts a clean strict
  build for a wrapper page.
- **C7 (Minor) — import path.** `zones_network` is in
  `prisma_access.network_services.models.zones_network`, not `...objects...` (Task B
  steps 1 & 8).
- **C8 (Minor, confirms) — verified correct on all 264 real wrappers:** `_direct_variants`
  order/types, `_is_container_branch` (0 false +/-; signature is exactly
  `{device,folder,snippet}`), the root-seeded cycle guard (no blanks). Counts: 264
  wrappers, 10 container-branch, 14 scalar-only.
- **C9 (validated across ALL specs) — classification swept every wrapper in every sub:
  264 wrappers across the 8 subs that have them (network_services 123, objects 49,
  security_services 36, identity_services 26, device_settings 22, config_setup 4,
  deployment_services/mobile_agent 2) → 0 crashes, 0 blank pages.** The other 6 subs
  (incidents, posture, ztna_connector, config_operations, …) carry NO wrapper models —
  plain-model path, unchanged. The field-table type renderer must handle the **192
  distinct payload-field annotation shapes** (buckets: 91 plain class, 74
  Optional-of-model `X | None`, 16 `List[...]`, 9 `Annotated[...]`, 2 `Dict[...]`):
  **reuse `from ..opmodel.introspect import _unwrap_optional`** (already used by
  examples.py) for both `Optional[X]` and PEP-604 `X | None`, unwrap `Annotated` via
  `get_args`, and format `list/dict` parameterized types as text. Add a type-formatter
  unit test covering one of each bucket.

---

## Architecture

Three independent changes, smallest-risk first:
- **A — global filter** (`mkdocs.yml.jinja`): add the two missing anyOf scaffolding
  patterns to the existing mkdocstrings filter. Fixes the visible leak alone; no-op
  for plain and oneOf pages.
- **B — inline wrapper rendering** (`gen_ref_pages.py.jinja`): a wrapper-aware variant
  resolver (validator-field driven, handles non-model variants), recursion to leaf
  models with a cycle guard, generic SCM-container detection + collapse, and grouped
  inline payload emission via per-leaf mkdocstrings blocks.
- **C — example synthesis** (`examples.py`): the same resolver shape so a wrapper body
  example picks a payload variant and emits a valid constructor. Duplicate logic by
  design (runs in the generator, not the built-SDK docs build — repo
  separation-of-duty; the two copies do not share code).

**Tech Stack:** Jinja2 templates emitting a `mkdocs_gen_files` Python script;
mkdocstrings-python + griffe-pydantic; pydantic v2 model introspection (`model_fields`,
`typing.get_args`/`get_origin`); pytest.

## Global Constraints
- **Generic, not per-spec.** Detection keys on shapes (validator-field names, the
  `folder`/`snippet`/`device` container signature), never on product/spec identifiers.
- **Plain (non-wrapper) pages stay byte-identical.** Wrapper pages (incl.
  prisma-browser's 9 oneOf pages) change by design — gate them with **semantic**
  assertions + a reviewed rendered snapshot, NOT byte-identity.
- **Never render a blank wrapper page.** A wrapper with only primitive/list variants
  must still list those variants.
- **Variant order = validator-field declaration order**, locked by test.
- **No new dependencies.** Use stdlib `typing`/`re` + pydantic already present.
- The docs build gate is `uv run nox -s sdk-docs` (mkdocs `--strict`); the offline
  gate (`uv run nox -s gate`) must stay green; update `.agents/context` + run
  `nox -s context` if a subsystem narrative changes.

---

## File structure

- `src/phantasos/scaffold/mkdocs.yml.jinja` — **modify** (Task A): +2 filter patterns.
- `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` — **modify** (Task B):
  replace `_oneof_variants`; add resolver + container detection + inline emission.
- `src/phantasos/generator/sdk/examples.py` — **modify** (Task C): wrapper-aware
  `_variants`/`_pick_variant`.
- `tests/test_sdk_docs_emitted.py` — **modify** (A: assert new filter patterns;
  B: replace the `actual_instance`/"One of the following variants" assertions with the
  inline-rendering assertions).
- `tests/test_examples.py` (or the existing examples test module) — **modify** (C).
- A new rendered-output test for B (see Task B step 8).

---

### Task A: anyOf scaffolding filter

**Files:**
- Modify: `src/phantasos/scaffold/mkdocs.yml.jinja:73` (end of the `filters:` list)
- Test: `tests/test_sdk_docs_emitted.py:235-242`

**Interfaces:**
- Produces: a global mkdocstrings filter that also suppresses `anyof_schema_*` and
  `any_of_schemas`. Tasks B/C do not depend on A.

- [ ] **Step 1: Write the failing test.** In
  `test_mkdocs_enables_griffe_pydantic_and_filters`, add to the asserted-pattern loop:
```python
    for pat in (
        "!^to_dict$",
        "!^model_config$",
        "!^additional_properties$",
        "!^actual_instance$",
        "!^oneof_schema_",
        "!^anyof_schema_",      # NEW
        "!^any_of_schemas$",    # NEW
    ):
        assert pat in mk, pat
```

- [ ] **Step 2: Run it, watch it fail.**
  `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pa uv run pytest tests/test_sdk_docs_emitted.py::test_mkdocs_enables_griffe_pydantic_and_filters -q`
  Expected: FAIL (`!^anyof_schema_` not in mk).

- [ ] **Step 3: Add the patterns.** In `mkdocs.yml.jinja`, after line 72
  (`- "!^oneof_schema_"`), add:
```yaml
              - "!^anyof_schema_"
              - "!^any_of_schemas$"
```

- [ ] **Step 4: Run it, watch it pass.** Same command → PASS.

- [ ] **Step 5: Verify no residual scaffolding against RENDERED output.** Build the
  prisma-access docs and confirm the `AddressGroups` page no longer shows
  `anyof_schema_`/`any_of_schemas`, AND check whether the anyOf validator *method*
  `actual_instance_must_validate_anyof` leaks (the oneOf form does not today, so it
  likely won't — but verify, don't assume):
  `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pa NOX_ENVDIR=$HOME/.tmp/pa-nox uv run nox -s sdk-docs`
  then grep the built `site/` (or the gen output) for those identifiers on a wrapper
  page. If `actual_instance_must_validate_` leaks, add `- "!actual_instance_must_validate"`.

- [ ] **Step 6: Commit.**
```bash
git add src/phantasos/scaffold/mkdocs.yml.jinja tests/test_sdk_docs_emitted.py
git commit -m "fix(sdk-docs): suppress anyOf wrapper scaffolding in the global filter"
```

---

### Task B: inline wrapper rendering (the core)

**Files:**
- Modify: `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja`
- Test (unit, against built models): `tests/test_sdk_docs_emitted.py` (new cases)
- Test (rendered): new `tests/test_sdk_docs_wrapper_rendering.py`

**Interfaces:**
- Consumes: built SDK models (`<pkg>.<sub>.models.*`), the global filter from Task A
  (independent — B works without A, A just removes residual scaffolding).
- Produces: per-wrapper-model reference pages with grouped inline payload + collapsed
  container; consistent for oneOf and anyOf.

The current generator (`gen_ref_pages.py.jinja`) has `_oneof_variants(model)` (reads
`actual_instance`'s Union) and, in `_emit`, the model loop writes `::: <module>` plus,
for a oneOf wrapper, a "One of the following variants:" link list. Replace that variant
logic with the resolver + inline emission below. **Do not** change `_emit`'s resource
(`_WRAPPERS`) loop or the federation/`_SUBPACKAGES` logic.

- [ ] **Step 1: Write failing unit tests** (`tests/test_sdk_docs_emitted.py`). Import
  the helpers the gen script will define (the script is a Jinja template, but the
  helper functions are plain Python rendered verbatim; test them by importing the
  rendered module OR — simpler — factor the helpers so the test exec's the rendered
  script and calls them. Match the existing test's approach of reading the rendered
  script text where structural, and add behavioral cases that exec the helpers against
  the real built `prisma_access` package on `sys.path`):
```python
def test_wrapper_resolver_handles_anyof_and_primitives() -> None:
    helpers = _load_gen_helpers()  # exec rendered gen_ref_pages.py, return its globals
    import prisma_access.objects.models.address_groups as ag
    import prisma_access.objects.models.zones_network as zn  # primitive/list variants
    assert helpers["_is_wrapper"](ag.AddressGroups)
    # anyOf: validator-field resolution (actual_instance is Any) -> direct variants
    direct = [t.__name__ for t in helpers["_direct_variants"](ag.AddressGroups)
              if isinstance(t, type)]
    assert "GroupType" in direct and "ContainerType" in direct
    # primitives are returned, not dropped:
    prim = helpers["_direct_variants"](zn.ZonesNetwork)
    assert prim  # non-empty (list/str types), never []

def test_container_branch_detected_and_payload_isolated() -> None:
    helpers = _load_gen_helpers()
    import prisma_access.objects.models.address_groups as ag
    branches = helpers["_classify_branches"](ag.AddressGroups)
    kinds = {b["label"]: b["kind"] for b in branches}
    assert kinds.get("ContainerType") == "container"
    assert kinds.get("GroupType") == "payload"
    payload_leaves = [l.__name__ for b in branches if b["kind"] == "payload"
                      for l in b["leaves"]]
    assert {"Static", "Dynamic"} <= set(payload_leaves)
```
  (Provide `_load_gen_helpers` in the test: render the template with a dummy
  `package="prisma_access"`, strip the `mkdocs_gen_files` import side effects by
  exec'ing only the helper defs, or wrap the helpers so import is side-effect-free.)

- [ ] **Step 2: Run, watch them fail** (helpers don't exist yet).

- [ ] **Step 3: Implement the resolver + classifier** in `gen_ref_pages.py.jinja`,
  replacing `_oneof_variants`. Add `import re`:
```python
import re

_VALIDATOR = re.compile(r"(any|one)of_schema_\d+_validator$")
_CONTAINER_FIELDS = {"folder", "snippet", "device"}


def _is_wrapper(model) -> bool:
    return isinstance(model, type) and issubclass(model, BaseModel) and any(
        _VALIDATOR.match(f) for f in model.model_fields
    )


def _direct_variants(model) -> list:
    """Variant types of a wrapper, in validator-field order, incl. non-model types.

    Validator-field resolution is the single signal (more robust than the
    `actual_instance` Union, which is typed `Any` at runtime for anyOf wrappers).
    """
    out = []
    for name, f in model.model_fields.items():
        if _VALIDATOR.match(name):
            ann = f.annotation
            args = get_args(ann)
            for a in (args if args else (ann,)):
                if a is not type(None):
                    out.append(a)
    seen, uniq = set(), []
    for a in out:
        if a not in seen:
            seen.add(a)
            uniq.append(a)
    return uniq


def _leaf_models(model, seen=None) -> list:
    """Field-bearing (non-wrapper) BaseModel leaves of a wrapper, de-duped, cycle-safe."""
    seen = seen if seen is not None else {model}
    leaves = []
    for v in _direct_variants(model):
        if not (isinstance(v, type) and issubclass(v, BaseModel)):
            continue  # primitives handled at the branch level
        if v in seen:
            continue
        seen.add(v)
        leaves += _leaf_models(v, seen) if _is_wrapper(v) else [v]
    return leaves


def _is_container_branch(variant) -> bool:
    """True iff `variant` is the SCM container: a wrapper whose every leaf carries
    exactly one real field (besides additional_properties) in {folder,snippet,device}."""
    if not _is_wrapper(variant):
        return False
    leaves = _leaf_models(variant)
    if not leaves:
        return False
    for leaf in leaves:
        real = [f for f in leaf.model_fields if f != "additional_properties"]
        if not (len(real) == 1 and real[0] in _CONTAINER_FIELDS):
            return False
    return True


def _type_label(t) -> str:
    """Render a non-model variant (str/list[str]/dict/number) as a code span."""
    origin = get_origin(t)
    if origin in (list, set):
        args = get_args(t)
        inner = _type_label(args[0]) if args else "Any"
        return f"`{origin.__name__}[{inner}]`"
    return f"`{getattr(t, '__name__', str(t))}`"


def _classify_branches(model) -> list:
    """One entry per direct variant: payload (with leaves) | container | scalar."""
    branches = []
    for v in _direct_variants(model):
        label = getattr(v, "__name__", str(v))
        if isinstance(v, type) and issubclass(v, BaseModel):
            if _is_container_branch(v):
                branches.append({"kind": "container", "label": label})
            elif _is_wrapper(v):
                branches.append({"kind": "payload", "label": label, "leaves": _leaf_models(v)})
            else:
                branches.append({"kind": "payload", "label": label, "leaves": [v]})
        else:
            branches.append({"kind": "scalar", "label": _type_label(v)})
    return branches
```

- [ ] **Step 4: Run the unit tests, watch them pass.**

- [ ] **Step 5: Wire the inline emission into `_emit`.** Where the model loop currently
  writes the page, branch on `_is_wrapper(model)`. For a wrapper, write the wrapper's
  own `:::` (the global filter from Task A hides its scaffolding, leaving the
  docstring), then the classified branches — per-leaf `:::` blocks under a heading for
  payload, a one-liner for container, a code-span list for scalars. Concretely, the
  per-model write becomes:
```python
        with mkdocs_gen_files.open(full, "w") as fd:
            fd.write(f"::: {dotted}\n")
            if _is_wrapper(model):
                branches = _classify_branches(model)
                payload = [b for b in branches if b["kind"] == "payload"]
                scalars = [b for b in branches if b["kind"] == "scalar"]
                has_container = any(b["kind"] == "container" for b in branches)
                for b in payload:
                    fd.write(f"\n**{b['label']} — one of:**\n\n")
                    for leaf in b["leaves"]:
                        leaf_dotted = f"{leaf.__module__}"
                        fd.write(f"::: {leaf_dotted}.{leaf.__name__}\n")
                if scalars:
                    fd.write("\n**Accepts:** " + " · ".join(b["label"] for b in scalars) + "\n")
                if has_container:
                    fd.write("\n**Placement:** `folder` · `snippet` · `device` "
                             "(standard SCM container)\n")
            elif variants:  # legacy non-wrapper-with-actual_instance path: keep nothing here
                pass
        mkdocs_gen_files.set_edit_path(full, path)
```
  Remove the old `_oneof_variants` call and its "One of the following variants:" block.
  (Single-variant payload renders as one `:::` with no awkward "one of"; a wrapper with
  only a container renders just the docstring + Placement line.)

- [ ] **Step 6: Update the structural test** at
  `tests/test_sdk_docs_emitted.py:263-265`. Replace:
```python
    assert "actual_instance" in script
    assert "One of the following variants" in script
```
  with assertions for the new surface:
```python
    assert "_is_wrapper" in script
    assert "_classify_branches" in script
    assert "Placement:" in script
    assert "One of the following variants" not in script  # old link list is gone
```

- [ ] **Step 7: Run the full emitted-docs test module, watch it pass.**
  `... uv run pytest tests/test_sdk_docs_emitted.py -q`

- [ ] **Step 8: Add a RENDERED-output test** (`tests/test_sdk_docs_wrapper_rendering.py`)
  gated on the built SDK toolchain (mirror existing slow/`_oag_toolchain_cached` gating
  if present). Build prisma-access docs and assert on the generated `reference/.../
  address_groups.md` (the `mkdocs_gen_files` virtual page — capture via the gen script
  or the built `site/`):
  - contains `Static` and `Dynamic` (payload leaves inline),
  - contains `Placement:` and does NOT contain `Folder`/`Snippet`/`Device` field blocks,
  - contains none of `anyof_schema_`, `any_of_schemas`, `actual_instance`,
  - a primitive wrapper page (`zones_network.md`) is non-empty / lists its scalar types,
  - a prisma-browser oneOf wrapper page (`policy_item.md`) renders inline payload
    (semantic: its variant model names present), NOT the old link list.
  Also assert a plain-model page (e.g. prisma-browser `device_group_request.md`) is
  unchanged vs a captured baseline.

- [ ] **Step 9: Run `nox -s sdk-docs` (`--strict`) for both products; fix any broken
  cross-references** the inline `:::` blocks introduce. Then `nox -s gate`.

- [ ] **Step 10: Review the prisma-browser wrapper-page diff** (9 oneOf pages) and the
  prisma-access wrapper pages by eye; capture the rendered snapshot the test pins.

- [ ] **Step 11: Commit.**
```bash
git add src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja tests/
git commit -m "feat(sdk-docs): inline payload fields on wrapper pages, collapse SCM container"
```

---

### Task C: synthesize_body wrapper-body example

**Files:**
- Modify: `src/phantasos/generator/sdk/examples.py:32-53`
- Test: the existing examples test module (find via `grep -rl synthesize_body tests/`)

**Interfaces:**
- Consumes: built SDK body models. Independent of A/B (separate mechanism; duplicate
  resolver by design — do not import from `gen_ref_pages`).
- Produces: a real payload-variant constructor for a wrapper body in the showcase guide.

- [ ] **Step 1: Failing test.** Assert the showcase-style body synthesizes a payload
  variant, not an opaque placeholder:
```python
def test_synthesize_body_picks_payload_variant_for_wrapper() -> None:
    import prisma_access.objects.models.address_groups as ag
    out = synthesize_body(ag.AddressGroups)
    assert "AddressGroups(...)" not in out          # not opaque
    assert "folder=" not in out and "snippet=" not in out  # container skipped
    assert "Static(" in out or "Dynamic(" in out    # a payload variant
```

- [ ] **Step 2: Run, watch it fail** (currently returns `AddressGroups(...)`).

- [ ] **Step 3: Make `_variants` wrapper-shape-aware** (mirror B's resolver, local to
  examples.py — no shared import). Replace the `actual_instance`-only body of
  `_variants` with validator-field resolution that returns model variants, and add a
  container skip + leaf descent in `_pick_variant`:
```python
import re
_VALIDATOR = re.compile(r"(any|one)of_schema_\d+_validator$")
_CONTAINER_FIELDS = {"folder", "snippet", "device"}

def _is_wrapper(model: type[BaseModel]) -> bool:
    return any(_VALIDATOR.match(f) for f in getattr(model, "model_fields", {}))

def _variants(model: type[BaseModel]) -> list[type[BaseModel]]:
    out: list[type[BaseModel]] = []
    for name, field in model.model_fields.items():
        if _VALIDATOR.match(name):
            for a in (get_args(field.annotation) or (field.annotation,)):
                if isinstance(a, type) and issubclass(a, BaseModel):
                    out.append(a)
    # de-dupe, preserve order
    seen: set[type] = set()
    return [a for a in out if not (a in seen or seen.add(a))]

def _is_container(model: type[BaseModel]) -> bool:
    if not _is_wrapper(model):
        return False
    for leaf in _variants(model):
        if _is_wrapper(leaf):
            return False
        real = [f for f in leaf.model_fields if f != "additional_properties"]
        if not (len(real) == 1 and real[0] in _CONTAINER_FIELDS):
            return False
    return True

def _pick_variant(model: type[BaseModel], variant: str | None) -> type[BaseModel] | None:
    vs = [v for v in _variants(model) if not _is_container(v)]  # skip container branch
    if variant:
        for v in vs:
            if v.__name__ == variant:
                return v
    return vs[0] if vs else None
```
  `_model_expr` already recurses through a picked wrapper variant, so a payload
  sub-wrapper (`GroupType`) descends to a leaf (`Static`) automatically. Verify whether
  the body must be wrapped (`AddressGroups(Static(...))`) or accepts the variant
  directly — check `AddressGroups.__init__`/pydantic coercion against the built model
  and emit the form the SDK actually accepts.

- [ ] **Step 4: Run the test, watch it pass.** Run the whole examples test module.

- [ ] **Step 5: Rebuild prisma-access docs; confirm the showcase guide `create`
  example now constructs a payload variant** (not `Addresses(...)`). `nox -s gate`.

- [ ] **Step 6: Commit.**
```bash
git add src/phantasos/generator/sdk/examples.py tests/
git commit -m "fix(sdk-docs): synthesize a payload-variant body example for wrapper bodies"
```

---

## Post-implementation
- Update `.agents/context/` (the sdk-docs deep-dive) narrative for wrapper rendering;
  `uv run nox -s context` (`-- --check` must pass).
- `CHANGELOG.md` `## [Unreleased]` entry.
- Whole-branch review (subagent-driven final review), then open the squash PR
  `--base develop`, no version bump.

## Test plan summary (edge cases that MUST have a test)
- anyOf wrapper (`AddressGroups`) → payload leaves inline, container collapsed.
- primitive/list-only wrapper (`ZonesNetwork`, `ApplicationsRisk`) → scalar variants
  listed, never blank.
- oneOf wrapper, both products (`GroupType`, prisma-browser `PolicyItem`) → inline,
  consistent.
- plain model (`DeviceGroupRequest`) → byte-identical to baseline.
- container-only wrapper → docstring + Placement line, no payload section.
- false-positive guard: a payload leaf that merely *has* a `folder` field (more than
  one real field) is NOT classified as container.
- variant order stable across rebuilds (assert fixed expected order for `AddressGroups`).
- `synthesize_body` on a wrapper body → payload variant, container skipped, not opaque.
