# Plan: model-page field-table rendering

- **Spec:** `docs/specs/2026-06-27-model-page-field-table.md` (handoff spec; authoritative for intent).
- **Branch:** continues on `feature/prisma-access-sdk` (same sdk-docs feature line).
- **Status:** **IMPLEMENTED + verified** (commit `62535ad`; the FORCE_COLOR test fix is `b2a82e5`). D1/D2 both confirmed Yes. `nox -s sdk-docs --strict` green for both products (every converted heading-only `:::` page keeps its anchor; R3 links + signature crossrefs resolve), `nox -s gate` green (663). Path A used (heading-only `:::` + `extensions: []` drops griffe-pydantic Config/Validators).
- **Gate:** offline `nox -s gate` after every commit; `nox -s sdk-docs` (`--strict`, both products) before declaring done; `nox -s context -- --check` after a narrative edit.

## Already handled (do NOT redo)

The spec's **Type column** is done. Commit `db6d567` (R3) shipped `_type_cell` in
`gen_ref_pages.py.jinja`: a field whose direct type is a *documented* model renders an
mkdocstrings autoref `[`Name`][module.Name]`, guarded by `_public_model(mod) is model`
so it never points at an ungenerated page; primitives stay plain. The base 3-column
`_field_table` (Field | Type | Required) and its tests also exist. **Remaining work:** the
page-body conversion, two more columns, capitalised `Yes`/`No`, model-level prose, and
extending the link to `list[Model]`.

---

## The crux — an autoref-anchor collision the spec under-specifies (resolve FIRST)

The spec says: *"The converted model page no longer emits the `::: module.Model` autodoc
block."* That instruction collides with the mechanism R3 just shipped.

**Evidence (captured this session):** an R3 cross-link resolves to
`../ldap_ldap/#prisma_access.identity_services.models.ldap_ldap.LdapLdap`. That anchor
(`#prisma_access…LdapLdap`) is the `ldap_ldap` **model page's mkdocstrings `:::` anchor**.
The resource pages' `signature_crossrefs` resolve the same way. So the model page's `:::`
is what *registers* the model identifier with autorefs.

**Therefore:** if a converted model page drops `:::`, the identifier `…LdapLdap` is no
longer registered → every inbound autoref (R3 field-table links **and** resource-page
signature cross-refs) becomes an unresolved reference → `mkdocs build --strict` aborts.
A converted page MUST still register its model identifier as an autoref anchor.

**Task 1 is a spike to choose the anchor mechanism.** Two paths:

- **Path A (recommended default) — keep a heading-only `:::`.** Render `::: module.Model`
  with per-block options that suppress the docstring, members, Config and Validators
  (`show_docstring: false`, `members: false`, …) so only the heading survives — registering
  the identifier *exactly as today* — then append the hand-rendered table below it. Zero
  change to how identifiers resolve → lowest risk. The spike must confirm griffe-pydantic's
  `Config:`/`Validators:` blocks can be fully suppressed (they may be tied to member
  rendering; if `members: false` doesn't drop them, A is out).
- **Path B (fallback) — drop `:::`, register an explicit autorefs anchor.** Emit the model
  identifier as an explicit mkdocs-autorefs anchor (markdown `[](){#module.Model}` /
  heading-id form) so `[text][module.Model]` still resolves. The spike must confirm the
  installed autorefs version registers a *dotted-identifier* anchor and that resolution is
  `--strict`-clean from another page.

**Decision gate:** if Path A cleanly suppresses the boilerplate → take A (least churn, no
resolver change). Else Path B. If *neither* yields a clean `--strict` build, fall back to
keeping the full `:::` and only ADDING the table beneath it (boilerplate remains — degraded,
but no breakage) and surface for a human.

> **Spike result (Task 1 — DONE, 2026-06-27): Path A CONFIRMED.** A heading-only
> `::: <module>.<Class>` with these options renders ONLY the anchored model-name heading:
> ```yaml
>     options:
>       extensions: []                     # disables griffe_pydantic for THIS block — the
>                                          # key that finally drops Config/Validators/Fields
>       members: false
>       show_docstring_description: false  # drops the OAG boilerplate description
>       show_root_heading: true            # keeps the heading -> registers the autoref anchor
>       show_bases: false                  # (+ other show_docstring_* false: belt & suspenders)
> ```
> A `mkdocs build --strict` on a griffe-pydantic fixture showed `Config`/`Validators`/field
> stanzas/OAG-description **all gone (counts 0)**, the anchor `id="<module>.<Class>"` still
> registered, and an inbound R3-style autoref still resolving
> (`href=".../foo/#spikepkg.models.foo.Foo"`). So a converted page = this heading-only `:::`
> (keeps the anchor R3 + signature_crossrefs depend on) **+** the hand-rendered one-liner **+**
> the 5-col table. **Caveat for D3:** `show_docstring_description: false` also drops a *genuine*
> one-liner, so the script must emit the kept SCM hint itself; the `:::` is purely heading+anchor.
> Tasks 2–7 are unblocked.

---

## Decisions to confirm (spec gaps)

- **D1 — One shared 5-col table, everywhere.** The spec says `_field_table` *becomes* the
  model-page body, and it is the same function feeding the wrapper-leaf inline tables
  (Task B). → Unify on one 5-column table; wrapper-leaf tables gain Default + Description
  and `Yes`/`No` too. This intentionally changes wrapper-page output and its tests.
  *Confirm: OK to make wrapper-leaf tables 5-col for consistency?* (Recommended yes.)
- **D2 — `list[Model]` display.** Spec: "unwrap `list[...]` to the inner type" and link if a
  model. Preserve the container — render `list[`[Model]`]` (inner model linked, `list[…]`
  kept) rather than a bare inner type. This extends `_type_cell` (R3 links direct models
  only) to link inside `list[…]`/`Optional[…]`. *Recommended over dropping list-ness.*
- **D3 — Boilerplate detection without the spec.** `gen_ref_pages` runs in the built SDK's
  docs venv (no spec access). Detect the OAG class-docstring boilerplate by **pattern** (the
  generic "This Open API Spec file… / Objects…" header) and drop it; keep a genuine
  one-liner (e.g. the SCM "Supply exactly one of folder/snippet/device…" hint that
  `flatten_scm_bodies` adds) as a single *italic* line above the table. Verify the exact
  boilerplate string against real built models. If pattern-matching is brittle, pass the
  known boilerplate text in via the template context (generator-side, which has the spec).
- **D4 — Default column.** `FieldInfo` default → code span; `PydanticUndefined`/no default →
  `—`; `default_factory` → `—`. Always present (uniform shape).

---

## Tiny-commit plan (TDD)

Gate-resident unit tests use **synthetic** models (no `prisma_access` import, per C3); the
end-to-end proof is `nox -s sdk-docs --strict`.

1. **Spike: resolve the anchor mechanism (Path A vs B).** Build a 2-page fixture (one page
   links `[text][x.Foo]`; the other is a table-only / heading-only-`:::` page for `Foo`) and
   prove the inbound link resolves under `mkdocs build --strict`. Output: a one-paragraph
   decision recorded at the top of this plan + the minimal scaffolding the chosen path needs.
2. **Extend `_field_table` to 5 columns** — add Default (D4) + Description; capitalise
   `Yes`/`No`. Update the field-table + wrapper unit/rendered tests for the new header/shape
   (D1: wrapper pages now 5-col).
3. **Extend `_type_cell` to link inside `list[…]`/`Optional[…]`** (D2) → `list[`[Model]`]`.
   Unit-test the container-with-model and the bare-scalar-list cases.
4. **Add the model-page converter.** A `_model_page(model)` branch in `_emit`: for a PLAIN
   (non-wrapper) model, emit heading + `_model_prose(model)` (D3) + the 5-col table, with the
   spike's anchor mechanism. Wrapper models keep Task B's variant treatment (leaves now
   5-col). No `:::` boilerplate on converted pages.
5. **Re-pin `test_plain_model_page_is_byte_identical_single_autodoc`** — it asserts the old
   `:::`-only output; the converted page is the new contract. Re-pin to the new shape and
   keep it a strict byte guard.
6. **Verify end-to-end** — `nox -s sdk-docs --strict` (both products); assert a real converted
   plain model page shows the 5-col table, its model-typed rows autoref-resolve, and carry no
   `Config:`/`Validators:`/boilerplate; a wrapper page still single-`:::` + variant tables
   (no regression). Then `nox -s gate`.
7. **Docs/wrap-up** — CHANGELOG `[Unreleased]` + `.agents/context/sdk-generator.md` narrative
   note (`nox -s context -- --check`); commit; squash PR `--base develop`, no version bump.

## Test plan (cases that MUST have a test)

- 5-col header + `Yes`/`No`; Default `—` vs value; Description `—` vs text.
- `list[Model]` links the inner model; `list[str]` stays plain; scalar/undocumented stays plain.
- Boilerplate docstring dropped; a genuine one-liner kept as one italic line.
- **The `--strict` anchor proof:** a converted page has no `:::` boilerplate, yet its identifier
  still resolves from an inbound autoref (the failure the spec missed).
- Wrapper pages unchanged structurally: exactly one `:::`, variant tables intact (no regression).
- `AddressGroups`-class real page (proof-of-done): 5-col table, `dynamic` row autoref resolves.

## Out of scope

- **Resource (`<Object>Resource`) pages stay autodoc** — they are the method surface (signatures
  + docstrings + `**Example:**`), not data shapes.
- `examples.py` / body synthesis — untouched (separation of duty).
- No new dependencies.

## Risk

Task 1 (the anchor mechanism) gates everything. Both R3's field-table links and the resource
pages' signature cross-refs depend on the model identifier staying registered; the conversion
must preserve that or `--strict` goes red. The plan front-loads it as a spike with a concrete
fallback (keep full `:::`, add table beneath) so the feature can't wedge.
