# Spec: model-page field-table rendering

**Status:** handoff spec (for the session implementing `_field_table`). Author session
delivered the rendered comparison (`~/addressgroups-ux-compare/`); this is the agreed
requirement.

## Intent

A consumer of a model page (e.g. `AddressGroups`) needs the **data shape**, not
pydantic/griffe internals. Today each model page renders the mkdocstrings+griffe
autodoc: a top API description (the OAG "This Open API Spec file…/Objects…" boilerplate),
a `Config:` block, every field as a prose stanza, and a `Validators:` block. Replace all
of that with **one field table**.

## The table

One row per field, in declaration order:

| Column | Content |
|---|---|
| **Field** | field name, code span |
| **Type** | the field's type (unwrap `Optional`/`Annotated`/`list[...]` to the inner type). If the inner type is another **generated model**, render an mkdocstrings **autoref** `[`ModelName`][module.ModelName]` → resolves to that model's page, `--strict`-safe. Scalars and undocumented / no-page models → plain `` `code` `` span. (Use the existing `_field_table` autoref mechanism — already tested.) |
| **Required** | `Yes` / `No` (capitalized, per the requirement) |
| **Default** | the field default as code, or `—` when none |
| **Description** | the field's schema `description`, or `—` |

## Replace the autodoc

The converted model page no longer emits the `::: module.Model` autodoc block (that block
is what pulls in `Config:`/`Validators:`/the boilerplate). It emits the page heading +
the table only. **This is the scope change**: `_field_table` currently feeds the
wrapper-leaf inline tables (Task B); here it *becomes* the model page body.

## Decisions (defaults chosen — override if you disagree)

- **(i) Model-level prose:** drop the OAG/spec boilerplate description entirely. If a model
  has a genuine, non-boilerplate one-liner (e.g. the SCM `Supply exactly one of
  folder/snippet/device…` hint), keep it as a single italic line *above* the table; else
  nothing but the table. Detection: a docstring equal to the spec `info.description` or the
  generic OAG header is boilerplate. → **default: keep a real one-liner, drop boilerplate.**
- **(ii) Default column:** **always present** (uniform table shape across all model pages;
  `—` when the field has no default) — not omitted per-model.

## Scope / where

- `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja` — the **model-page** rendering
  path (currently the autodoc `:::`).
- **Distinct from wrapper pages.** Task B's inline variant tables (oneOf/anyOf wrappers)
  already render those; don't regress them.
- Preserve the existing `--strict` byte-identity invariant for any page **not** converted
  (`test_sdk_docs_wrapper_rendering.py` / `test_sdk_docs_emitted.py` guard it).

## Proof of done

- `mkdocs build --strict` green for **both** products.
- A real model page (e.g. `AddressGroups`) shows the 5-column table; the `dynamic` row's
  `AddressGroupsDynamic` autoref resolves to its page; **no** `Config:`/`Validators:`/
  boilerplate on converted pages.
- Scalars stay plain code spans; an undocumented model type is a plain span (no broken
  autoref).
