# SDK reference docs: rendering anyOf/oneOf wrapper models

**Status:** rev 3 — grilled & final; ready for implementation plan
**Date:** 2026-06-27
**Scope:** `src/phantasos/scaffold/mkdocs.yml.jinja` (global mkdocstrings filter) +
`src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` (the variant resolver).
**Affects:** products whose specs use openapi-generator anyOf wrapper models (the
prisma-access SCM specs). oneOf wrappers — including prisma-browser's nine — already
render correctly today and must stay unchanged.

---

## REV 3 — FINAL design (grilled 2026-06-27)

The grill chose a **richer presentation than the reviewers' minimal fix**: instead of
linking variants, **inline the payload fields** on every wrapper page. The reviews
remain authoritative for the *diagnosis*, for **Task A** (the filter), and for the
mechanics (validator-field resolution, non-model variants, semantic — not
byte-identity — regression). Tasks B/C implement the grilled design on top.

### The wrapper page (final)
A wrapper model's page renders its **payload** branch fields inline, grouped, with the
SCM **container** branch collapsed to one line. Applies to **all** wrapper pages
(oneOf + anyOf, both products) for consistency.

```
AddressGroups
=============
A group address object.

Members — one of:
  Static    static: list[str]
  Dynamic   dynamic: str

Placement: folder · snippet · device   (standard SCM container)
```

### Resolved decisions
- **Page shape = inline fields** (not links, not a flat leaf list). Recurse through
  wrapper layers to the field-bearing leaves.
- **Grouped by branch.** Each non-container branch is a labelled group of its leaves'
  inline fields. Payload is foregrounded.
- **Collapse the container branch.** A branch is the SCM *container* iff its leaves
  each carry a single field in `{folder, snippet, device}` (+ `additional_properties`).
  Render it as a one-line `Placement: folder · snippet · device`, not field blocks.
  Generic (≈110 models), no per-spec code. Needs a **tight signature + false-positive
  test** (a real payload leaf that merely *has* a `folder` field must not trip it —
  require the leaf to have ONLY that field beyond `additional_properties`).
- **Scope = all wrapper pages.** prisma-browser's 9 oneOf pages change (links → inline
  fields — an improvement). Regression gate is **semantic** (variants/fields present,
  scaffolding absent) plus a **reviewed rendered snapshot**; non-wrapper (plain) pages
  stay byte-identical.
- **Primitive/non-model variants** (`ApplicationsRisk = str|int`, `ZonesNetwork =
  list[str]`): render as inline code spans, never dropped, never blank.
- **Variant order:** validator-field declaration order (carries resolved types),
  locked with a test.
- **Leaf models keep their own standalone pages** (the inline duplication is accepted).
- **synthesize_body (Task C) IS in scope.** The showcase body `Addresses` is itself a
  wrapper, so the quickstart `create` example renders an opaque `Addresses(...)`. Fix
  `examples.py` to pick a **payload** variant (skip the container branch) and emit a
  valid constructor (e.g. `Static(static=[...])`). Separate mechanism from B (runs in
  the generator, not the built-SDK docs build) — duplicate logic, do not share code
  (repo separation-of-duty).

### Tasks (grilled split)
- **Task A — leak filter.** `mkdocs.yml.jinja`: add `!^anyof_schema_` and
  `!^any_of_schemas$` to the global filter (and verify the anyOf validator *method*
  `actual_instance_must_validate_anyof` is covered against rendered output). Risk-free,
  no-op for plain/oneOf pages, ships first.
- **Task B — inline wrapper rendering.** `gen_ref_pages.py.jinja`: variant resolver
  (primary `actual_instance` Union → fallback validator fields for the `Any` case),
  recurse-to-leaves with a cycle guard seeded by the root, container detection +
  collapse, grouped inline payload (mkdocstrings `:::` per payload leaf), code-span
  primitives, keyword-faithful headings. Update
  `tests/test_sdk_docs_emitted.py:227-242,263-265`. Semantic + rendered-`.md` tests;
  reviewed browser snapshot.
- **Task C — example synthesis.** `examples.py`: same fallback resolver + container
  skip; emit a valid payload-variant constructor for a wrapper body.

### Deviation note
This final design is materially larger than the two python-pro reviews scoped (they
recommended one-level links + the filter). The grill deliberately chose inline payload
+ container collapse + the synthesize_body fix. The reviewers' blockers still bind:
Task A is exactly their filter fix; Task B must handle non-model variants (else blank
pages) and use semantic regression (browser is NOT byte-identical). Worth a second,
shorter review of Tasks B/C once planned, given they exceed what was reviewed.

---

## REV 2 — corrected design (after two python-pro reviews)

The original §4 design (below, kept as record) was the right diagnosis but an
oversized, partly-wrong cure. Two independent python-pro reviews, both validated
against the built SDKs, corrected it. The **actual** broken surface and fix:

**What's really broken:** only **anyOf** wrappers (where `actual_instance` is `Any`
at runtime). oneOf wrappers — `GroupType`, `ContainerType`, and prisma-browser's nine
(`ApplicationItem`, `PolicyItem`, `PositionItem`, …) — type `actual_instance` as a
real `Union` and already render their variant lists correctly. So the broken surface
is **anyOf tops only** (`AddressGroups` and ~20 others), not "all SCM wrappers."

**The two leaks on an anyOf page, and their fixes:**

1. **Scaffolding leak.** A global mkdocstrings filter ALREADY exists
   (`mkdocs.yml.jinja:58-73`) suppressing `actual_instance`, `one_of_schemas`,
   `oneof_schema_`, `to_json`/`to_dict`/… — but only the *oneOf* forms. The anyOf
   forms (`anyof_schema_`, `any_of_schemas`) were never added. **Fix A:** add
   `!^anyof_schema_` and `!^any_of_schemas$` to that global filter. ~2 lines, no-op
   for plain and oneOf pages, fixes the visible leak on every anyOf page. This alone
   resolves the reviewer's literal complaint ("shows oneOf internals") and can ship
   as an independent first commit.

2. **No variant links.** The resolver `_oneof_variants` reads `actual_instance`'s
   `Union` — `Any` for anyOf → returns `[]` → no "one of …" block. **Fix B:** keep
   `_oneof_variants` as the **primary** resolver (so the nine browser oneOf pages and
   the SCM oneOf pages stay byte-identical), and add a **fallback** that fires only
   when it returns `[]`: read the typed `{any,one}of_schema_N_validator` fields.
   **One level only** — do NOT recurse to leaves: `AddressGroups → [GroupType,
   ContainerType]`, and those child pages already render their own variants, so the
   user navigates a faithful tree. **Render non-BaseModel variants** (`str`,
   `list[str]`, `dict`, numbers) by name — dropping them (the original BaseModel-only
   filter) blanks ~16 pages. Label by the actual keyword: **"Any of the following
   variants:"** for the anyOf fallback, keeping **"One of the following variants:"**
   for the unchanged oneOf path.

**Dropped from rev 1:** the resolver *swap* (→ reordered browser pages), leaf
**recursion** (→ flattened structure, less honest, cycle risk), per-identifier
`filters` (→ clobber the global list, since mkdocstrings replaces rather than merges
list options), and the byte-identity-vs-all-browser claim (false — browser has nine
oneOf pages; the correct invariant is "the primary path is untouched, so oneOf +
plain pages are byte-identical; only anyOf pages change").

**Decisions settled by the reviews:** D1 → link direct (one-level) variants, existing
bullet format. D3 → extend the global filter (not per-identifier, not `members:false`).
D4 → one level, drop `_leaf_models`. D6 → moot (no recursion).

**Still open for the grill (consolidated):**
- **G1 — Ship split?** Fix A (global filter) alone fixes the visible leak and is
  risk-free — ship it as commit 1, then Fix B (variant links) as commit 2? Or together?
- **G2 — Primitive-variant presentation.** How to render `str` / `list[str]` / `dict`
  / number variants on a wrapper page (inline code spans?). ~21 pages. (rev-1 D-series
  never covered non-model variants.)
- **G3 — anyOf honesty (was D2).** `AddressGroups` is anyOf of a *group type* AND a
  *container* — semantically a combination, not a pick-one. Reviewers recommend the
  keyword-faithful "Any of …" and NOT asserting "needs both" (inferred). You know the
  API — is keyword-faithful enough, or should the docs hint at the combination?
- **G4 — Variant order for the anyOf fallback.** Validator-field order vs the
  `*_OF_SCHEMAS` string constant disagree (`AddressGroups`: validators give
  `[GroupType, ContainerType]`, constant gives `[ContainerType, GroupType]`). Pick one,
  lock it with a test.
- **G5 — `synthesize_body` / `examples.py` (was D5).** The body-example generator has
  a *duplicate* `_is_wrapper`/`_variants` with the same `actual_instance` assumption
  (`examples.py:32-42`); it degrades a wrapper body to an opaque `AddressGroups(...)`
  placeholder (confusing, not a leak). Fix in this spec or a sibling follow-up? (Can't
  share code — one runs in the generator, the other in the built SDK's docs build.)
- **G6 — Residual methods.** Verify Fix A's two patterns fully clean the page — the
  anyOf *validator method* (`actual_instance_must_validate_anyof`) may need covering
  too; confirm against rendered output, not assumption.

**Tests (rev 2):** unit on the fallback resolver against real models (`AddressGroups`
→ `[GroupType, ContainerType]`; a primitive-variant wrapper like `ZonesNetwork` /
`ApplicationsRisk` → non-empty, never blank; a plain model → not a wrapper); update
the existing `tests/test_sdk_docs_emitted.py:227-242,263-265` (which pin the global
filter list and the `actual_instance` / "One of the following variants" strings);
rendered-`.md` assertions that an anyOf page shows its variants and none of the
suppressed identifiers; oneOf + plain pages unchanged (primary path untouched).

---

---

## 1. Problem

A reviewer of the generated prisma-access docs found that a resource body's model
page shows openapi-generator's anyOf/oneOf **scaffolding** instead of the data
model. Concretely, `AddressGroupResource.create(body: AddressGroups)` links to the
`AddressGroups` page, which renders only:

```
anyof_schema_1_validator, anyof_schema_2_validator, actual_instance, any_of_schemas
```

— plus the wrapper's `from_json`/`to_json`/validator methods. None of the actual
address-group fields appear, and there is no path to the models that do carry them.

The same machinery produces correct, useful pages for prisma-browser. So the report
framed this as "the docs need spec-specific wiring." This spec argues the opposite:
it is **one generic gap** in handling the anyOf/oneOf wrapper shape, and a single
fix covers all current and future specs.

## 2. Root cause (verified against the built SDK)

The reference generator resolves a wrapper's variants with `_oneof_variants`, which
reads the type annotation of the `actual_instance` field and returns its `Union[...]`
members:

```python
field = model.model_fields.get("actual_instance")
inner = field.annotation
if get_origin(inner) in (Union, UnionType):
    return [a for a in get_args(inner) if <BaseModel subclass>]
return []
```

Two facts break this for the SCM models (both confirmed by introspecting the built
`prisma_access` package):

1. **`actual_instance` is typed `Any` at runtime.** openapi-generator emits the real
   `Union[ContainerType, GroupType]` annotation only under `if TYPE_CHECKING:`; the
   runtime field is `actual_instance: Any = None`. So `get_origin(Any)` is `None` and
   `_oneof_variants` returns `[]` — zero variants, nothing but scaffolding rendered.
   (prisma-browser happened to expose `actual_instance` as a real `Union`, which is
   why its oneOf pages — where it has any — worked.)

2. **Wrappers nest.** `AddressGroups` (anyOf) → `GroupType` and `ContainerType`, each
   of which is itself a oneOf wrapper. The field-bearing leaf models are two levels
   down:

   ```
   AddressGroups            [anyOf wrapper]
   ├─ GroupType             [oneOf wrapper] → Static {static}, Dynamic {dynamic}
   └─ ContainerType         [oneOf wrapper] → Folder {folder}, Snippet {snippet}, Device {device}
   ```

The reliable variant signal is NOT `actual_instance` — it is the typed
`{any,one}of_schema_N_validator: Optional[Variant]` fields (and/or the
`<NAME>_{ANY,ONE}_OF_SCHEMAS` class lists) that every wrapper carries regardless of
how `actual_instance` is typed.

### Why prisma-browser is unaffected

prisma-browser's body models are plain pydantic models (`DeviceGroupRequest`:
`name, platform, attributes, …`) — no wrapper fields. Its pages must remain
**byte-identical** after this change.

## 3. Goals / non-goals

**Goals**
- A wrapper model's reference page shows the user the real shapes the body accepts,
  not openapi-generator scaffolding.
- Generic: driven by the wrapper shape, not per-spec code or config.
- Single-spec output (prisma-browser) byte-identical; plain models unchanged.

**Non-goals**
- Changing the generated SDK models (the wrapper shape is OAG's; we render it, not
  reshape it). SDK ergonomics / oneOf-flattening at the model layer is out of scope.
- The CLI's separate oneOf-wrapper output leak (tracked elsewhere).

## 4. Proposed design

Three changes to `gen_ref_pages.py.jinja`, all in the reference generator:

### 4.1 Generic variant resolution
Replace `_oneof_variants` with a resolver keyed on the validator fields:

```python
_VALIDATOR = re.compile(r"(any|one)of_schema_\d+_validator$")

def _is_wrapper(model) -> bool:
    return any(_VALIDATOR.match(f) for f in model.model_fields)

def _direct_variants(model) -> list[type]:
    out = []
    for name, f in model.model_fields.items():
        if _VALIDATOR.match(name):
            for a in (get_args(f.annotation) or (f.annotation,)):
                if isinstance(a, type) and issubclass(a, BaseModel):
                    out.append(a)
    return out   # preserves declaration order; de-dupe by identity at call site
```

This handles anyOf, oneOf, and the `actual_instance: Any` case uniformly. The old
`actual_instance`-Union path is subsumed (and can be kept as a fallback for any
generator variant that types it directly).

### 4.2 Recurse to leaf models
`AddressGroups` → fragments that are themselves wrappers. Resolve recursively to the
**leaf** (non-wrapper) data models, de-duped, cycle-guarded:

```python
def _leaf_models(model, seen=None) -> list[type]:
    seen = seen or set()
    leaves = []
    for v in _direct_variants(model):
        if v in seen: continue
        seen.add(v)
        leaves += _leaf_models(v, seen) if _is_wrapper(v) else [v]
    return leaves   # AddressGroups -> [Static, Dynamic, Folder, Snippet, Device]
```

### 4.3 Suppress scaffolding + present the variants
On a wrapper's page, hide the scaffolding and show the resolved shapes. Emit
mkdocstrings per-identifier options to filter wrapper noise, then list the variants:

```
::: prisma_access.objects.models.address_groups.AddressGroups
    options:
      filters: ["!^anyof_schema_", "!^oneof_schema_", "!^actual_instance$",
                "!_of_schemas$", "!^from_json$", "!^to_json$", "!^to_dict$",
                "!^from_dict$", "!^to_str$"]

**Accepts one of:**

- [Static](static.md) · [Dynamic](dynamic.md) · [Folder](folder.md) ·
  [Snippet](snippet.md) · [Device](device.md)
```

(The exact filter list and whether `members: false` is cleaner than per-name filters
is an implementation detail to settle against real mkdocstrings output.)

## 5. Open design decisions (for the grill)

- **D1 — Variant presentation.** Three options for a fragmented wrapper body:
  (a) **link** the leaf models (smallest change; user assembles the shape);
  (b) **inline** each leaf's fields on the wrapper page (one-page shape, more render
  work, risk of duplicating model docs); (c) **show the tree** (`AddressGroups =
  GroupType{Static|Dynamic} + ContainerType{Folder|Snippet|Device}`) to convey that
  some specs need a *combination*, not a choice. Recommendation: (a) + a one-line tree
  caption, but this is the key call.
- **D2 — "Choice" vs "combination" honesty.** `AddressGroups` is `anyOf` of a *group
  type* and a *container* — semantically the body needs BOTH, but the model says
  "any of." Do the docs present it as "one of" (literal to the model) or explain the
  combination (accurate to the API but inferred)? Over-claiming risks misleading;
  under-claiming is what we have now.
- **D3 — Scaffolding suppression mechanism.** Per-name `filters` vs `members: false`
  vs a docstring-only stub. Which yields the cleanest page and survives mkdocstrings
  upgrades?
- **D4 — Leaf vs one-level variants.** Recurse all the way to leaves (5 models), or
  show one level (`GroupType`, `ContainerType`) and let the user click down? Leaves
  are more actionable; one level mirrors the type signature.
- **D5 — Scope creep.** Does this also touch `synthesize_body` (the Tier-1 body
  example samples), which would emit equally confusing scaffolding for a wrapper body?
  In-scope now or follow-up?
- **D6 — Cycle/self-reference safety.** Recursive/self-referential anyOf schemas exist
  in the wild; the cycle guard must be proven, not assumed.

## 6. Risks

- **Shared scaffold.** `gen_ref_pages.py.jinja` serves both single-spec and federated
  builds. A regression hits prisma-browser. Mitigation: a byte-identity assertion on
  prisma-browser reference output, plus the existing `nox -s sdk-docs --strict` gate.
- **mkdocstrings coupling.** Filter syntax / behavior is mkdocstrings-version-specific.
  Mitigation: pin behavior with a rendered-output test, not just a unit test.
- **Generator drift.** Future OAG versions may change wrapper field names. Mitigation:
  the resolver keys on a documented naming pattern; a test asserts detection on a
  real wrapper so drift fails loudly.

## 7. Test plan

- Unit: `_is_wrapper` / `_direct_variants` / `_leaf_models` against real built models
  (`AddressGroups` → `[Static, Dynamic, Folder, Snippet, Device]`; a plain model → not
  a wrapper; a cyclic synthetic wrapper terminates).
- Rendered: build prisma-access docs `--strict`; assert the `AddressGroups` page
  contains the variant links and none of the suppressed scaffolding identifiers.
- Regression: prisma-browser reference pages byte-identical to pre-change.

## 8. Alternatives considered

- **Per-spec docs adaptations** (the original framing): rejected — N specs, ongoing
  maintenance, and the shape is generic, not per-spec.
- **Reshape the SDK models (flatten anyOf/oneOf)** so bodies are plain: out of scope
  and far larger; the "oneOf-flatten ceiling" is a known hard problem at the model
  layer. This spec is docs-only.
- **Document only one level (no recursion):** simpler but leaves the user two clicks
  from any real field on a deeply nested wrapper.
