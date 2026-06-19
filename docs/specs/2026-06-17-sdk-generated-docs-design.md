# Generated-SDK user documentation (mkdocs) — design

- **Date:** 2026-06-17
- **Status:** Draft (post-grill, spikes resolved 2026-06-18, pre-plan)
- **Branch:** `feature/sdk-generated-docs`
- **Owner:** Oliver Kaiser

## 1. Problem & motivation

A generated SDK today ships a **broken documentation shell**: the scaffold emits
`mkdocs.yml` (Material + mkdocstrings, nav = Home + API Reference) and a
`.github/workflows/docs.yml` Pages deploy, but **no `docs/` content, no
`docs` dependency group, and no docs nox sessions**. The emitted `mkdocs.yml`
points at `index.md` / `reference.md` that don't exist, and the workflow's
`uv run --group docs mkdocs build --strict` would fail because the group and
the mkdocstrings dependency aren't declared. Net: there is essentially **no
working user documentation for generated SDKs** — only a latent, non-building
scaffold.

We want production-grade, mostly auto-generated user docs for each generated
SDK — in the spirit of phantasos's own Material site, but richer: a quickstart,
an architecture page, task-oriented how-to guides for **authentication,
pagination, and CRUD**, and an auto-generated **API reference** so consumers can
browse the available resources, operations, and models.

## 2. Goals / non-goals

**Goals**
- Generate a complete, strictly-building Material for MkDocs site into each
  opted-in generated SDK.
- Page set (Diátaxis-aligned): **Home**, **Getting Started** (tutorial),
  **Architecture** (explanation), **Guides** (how-to: auth / pagination / CRUD),
  **API Reference** (auto-generated).
- The how-to guides show **real, runnable** examples for an author-named
  showcase resource (accurate method names, request models, params).
- Reference is auto-generated from emitted docstrings via mkdocstrings, covering
  `api` + `models`.
- Everything is **config-gated**: a product opts in via a `docs:` block; nothing
  docs-related is emitted otherwise (this also *fixes* the broken shell for
  non-docs products by making it conditional).
- The whole pipeline is verified end-to-end by a real `mkdocs build --strict`.

**Non-goals**
- No per-symbol curated reference rendered from `OperationInventory` (we chose
  mkdocstrings autodoc for the reference). The curated metadata is used only to
  tailor the *guides*.
- No autodoc of the `extras` helpers (facade/auth/pagination) — those are taught
  in the guides, not the reference.
- No multi-resource guide matrix; one author-named showcase resource drives the
  tailored examples.
- Not changing how phantasos's *own* docs are built.

## 3. Locked decisions (from the grill)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Reference content | **mkdocstrings autodoc** (griffe); completes the latent scaffold |
| 2 | Guide tailoring | **Author-specified showcase resource** (in a product-config `docs:` block) |
| 3 | Example accuracy | **Scoped introspect** of the showcase resource (real names/models/params) |
| 4 | Trigger & default | **Post-build stage of `sdk build`, config-gated** (off unless `docs:` present) |
| 5 | Architecture page | **Auto-generated from `has_*` descriptors + Mermaid** (phantasos style) |
| 6 | First delivery | **Full feature in one PR** |
| 7 | Partial CRUD | **Render only operations that exist** (per scoped introspect) |
| 8 | Reference breadth | **`api` + `models`** (helpers covered by guides, not autodoc) |
| 9 | Verification gate | **New nox docs gate** (real SDK → real docs → `mkdocs build --strict`) + emitted-file behavioral tests |

## 4. Architecture & data flow

The docs stage lives inside `generator/sdk/build.py`, reusing the existing
scaffold engine. The key fact that makes this clean: `introspect()`
(`generator/cli/introspect.py:196`) runs **in-process** by inserting the SDK
path into `sys.path`, importing `<package>.extras.facade`, and reading
`facade._RESOURCES`. In `build.build()` that module exists immediately after the
**vendor** step (4) and before the **scaffold** step (4b).

```
build.build():
  1 preprocess
  2 generate            -> <package>/api, models, ...
  3 patches
  4 vendor              -> <package>/extras/{facade,auth,pagination,...}.py   (facade._RESOURCES now exists)
  4a DOCS INTROSPECT    [NEW, only if cfg.docs]  -> scoped OperationInventory for the showcase resource
                                                 -> build docs_context (operations, credentials, flags)
  4b scaffold render    -> render_scaffold(builtin, overrides, out_dir, {**loaded.context, **docs_context})
                          docs/*.jinja gated on has_docs render the site; non-docs builds skip them (whitespace gate)
  5 provenance
  6 smoke
```

- The docs templates are **ordinary gated scaffold templates** under
  `src/phantasos/scaffold/docs/`. When `has_docs` is false they render to
  whitespace and `render_scaffold` skips them (existing gating mechanism,
  `scaffold.py:55`).
- No change to `LoadedProduct`. `build.py` passes an enriched context dict
  (`{**loaded.context, **docs_context}`) to `render_scaffold` only for the docs
  pages. (Implementation note: pass the merged dict as the single `context`
  argument — load-time context is unaffected for non-docs products.)
- The **API reference** does *not* need introspect: it is produced at the SDK's
  own `mkdocs build` time by mkdocstrings via a generated `gen_ref_pages.py`
  (gen-files) + literate-nav. Only the **guides** and the **getting-started**
  first-call use the introspect results.

## 5. Config surface

New `DocsConfig` model + a `docs` field on `ProductConfig`
(`productconfig.py`). `docs` absent ⇒ feature off.

```python
class DocsOperations(BaseModel):       # optional per-verb method-name override
    model_config = ConfigDict(extra="forbid")
    create: str | None = None
    read: str | None = None            # the "get one" op
    list: str | None = None
    update: str | None = None
    delete: str | None = None

class DocsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    showcase_resource: str             # facade _RESOURCES key, e.g. "applications"
    site_name: str | None = None       # defaults to project.distribution
    operations: DocsOperations | None = None  # pin exact methods when the heuristic is wrong
```

`sdk.yml` (prisma-browser) gains:

```yaml
docs:
  showcase_resource: applications
```

- Presence of `docs:` ⇒ `has_docs = True`. `showcase_resource` is **required**
  when `docs:` is present (the guides are the point of the feature).
- `showcase_resource` is validated at the docs-introspect step against
  `facade._RESOURCES`; an unknown name fails the build with the available list
  (fail-fast, build-time — consistent with the repo's "clear error" ethos).

## 6. Context enrichment (`docs_context`)

Built in `build.py` (new helper, e.g. `generator/sdk/docs.py::build_docs_context`)
from the scoped introspect + the loaded components:

- `has_docs: bool`
- `site_name: str`
- `showcase` — the resource's tailored operation data:
  - `attr` (e.g. `application`), `api_cls`
  - `operations`: the verbs that **actually exist**, each with method name,
    request model name + required fields, id/path params, list/`items_field`,
    return model. Derived by filtering the scoped `OperationInventory` and
    classifying create/list/get/update/delete by method-name prefix +
    signature shape.
  - convenience flags: `has_create`, `has_list`, `has_get`, `has_update`,
    `has_delete` (drive partial-CRUD rendering).
- `credentials` — from `loaded.auth.credential_fields()` (name, env_var,
  secret, required, client_kwarg): drives the auth guide + getting-started.
- existing `has_auth/has_pagination/has_errors/has_facade/has_retry`,
  `package`, `library`, `distribution`, `repo_url`, etc. (already in context).

`has_docs` is also added to the **load-time** context (derived from
`cfg.docs is not None`) and to `_AUTO_EXPOSED` so it's available to the
always-emitted templates we gate (mkdocs.yml, pyproject, noxfile, docs.yml).

## 7. Scoped introspect & verb classification

- Reuse `introspect.introspect(package, sdk_path)`; filter
  `inventory.operations` to `op.resource == showcase_resource`.
- **Verb classification is a heuristic, not a clean prefix map** — verified
  against the real `applications` resource, whose methods are
  `create_application`, `bulk_create_applications`, `get_application_by_id`,
  `get_application_by_type_and_id`, `list_applications`,
  `list_applications_by_type`, `list_application_categories`,
  `patch_application_by_type_and_id`, `delete_application_by_id`,
  `delete_application_by_type_and_id`, `bulk_delete_applications`. The rule:
  1. Map the leading verb token to a CRUD slot
     (`create`→create, `get`→read, `list`→list, `update`/`patch`/`put`→update,
     `delete`→delete).
  2. Within a slot, **exclude `bulk_`** and pick the **canonical** op: prefer
     the method whose name matches the resource noun (singular for
     create/read/delete, plural for list) and has the **fewest required path
     params** (so `get_application_by_id` beats `get_application_by_type_and_id`;
     `list_applications` beats `list_applications_by_type`; a different-noun op
     like `list_application_categories` is rejected by the noun match).
  3. A `docs.operations` override pins the exact method per slot when the
     heuristic is wrong. Only slots that resolve to a real method are rendered
     (decision #7).
- Request-model name + required fields come straight from `ParamInfo.body_model`
  / `body_fields`; **examples render every required param** (path + body) — the
  canonical `create_application` still requires a `type` path arg, so the
  snippet must include it (use `enum_values` if present, else a `"<type>"`
  placeholder).
- **sys.modules caveat (latent, not triggered today):** `introspect()` restores
  `sys.path` but leaves the imported `<package>*` modules in `sys.modules`. Every
  current flow builds one product per process (`sdk build`; `smoke`/`live` use
  separate subprocesses), so the 4a import is safe. If `build()` is ever called
  twice in one process, evict `<package>*` from `sys.modules` first.
- **Dependency note — VERIFIED (spike 1):** `introspect()` imports the generated
  package; its runtime deps (`urllib3`, `python-dateutil`, `pydantic`,
  `typing-extensions`) import cleanly in the phantasos env, and a scoped
  introspect of the real built prisma-browser SDK returned all 13 resources
  in-process. No subprocess fallback needed.

## 8. Emitted documentation files

All under `src/phantasos/scaffold/`, all `.jinja`, all gated on `has_docs`
(render to whitespace ⇒ skipped when off). Per-product overrides win by path
(`products/<name>/overrides/docs/...`) via the existing scaffold mechanism.

- `docs/index.md.jinja` — **Home**: what the SDK is, install, 30-second value
  prop, signposts to the four sections.
- `docs/getting-started.md.jinja` — **Tutorial**: pinned install, auth-first
  (`Client.from_env()` + required env vars from `credentials`), first real call
  using the showcase resource's list/get, expected-shape note.
- `docs/architecture.md.jinja` — **Explanation**: client lifecycle (reuse one
  client), the resource/operation/facade model, which components this SDK has
  (driven by `has_auth/has_pagination/has_retry/has_errors`), plus a **Mermaid**
  diagram. No claims about absent components.
- `docs/guides/authentication.md.jinja` — from `credentials`: required vs
  optional env vars, secret handling, `from_env()` vs `from_credentials()`,
  precedence. Gated on `has_auth`.
- `docs/guides/pagination.md.jinja` — `Client.paginate(list_method, **filters)`
  over the showcase list op; iterator-first, note truncation. Gated on
  `has_pagination` **and** `showcase.has_list`.
- `docs/guides/crud.md.jinja` — create → get → (update) → (delete) for the
  showcase resource, only the verbs that exist, each runnable, cross-linked to
  the reference.
- `docs/scripts/gen_ref_pages.py.jinja` — gen-files script: walk `<package>/api`
  and `<package>/models`, emit one `reference/<module>.md` with a `:::` directive
  per module and a `reference/SUMMARY.md` for literate-nav. (Static w.r.t.
  introspect; runs at the SDK's mkdocs build time. Skips `extras`, `_about`,
  package root — breadth = api + models, decision #8.)
- `docs/_hooks.py.jinja` — **MkDocs `hooks:` logging filter** (verified in
  spike 3): drops only griffe's benign `Duplicate parameter information`
  records so `mkdocs build --strict` passes while still failing on real
  problems (broken links, missing nav). Cause: OAG emits each param's
  description in *both* the sphinx docstring and the
  `Annotated[..., Field(description=...)]` annotation; griffe flags the overlap.
  This is not suppressible via mkdocstrings render options (it fires at
  parse time) — the hook is the mechanism that keeps **both** decision #1
  (autodoc) and decision #9 (strict).

## 9. Scaffold wiring changes (existing templates → gated)

**Gating idiom (verified, spike-round-2):** every gated template uses
`{% if has_docs | default(false) %}` — NOT bare `{% if has_docs %}`. Under the
scaffold's `StrictUndefined`, a bare reference raises `UndefinedError` whenever a
render context omits `has_docs` (the existing `tests/test_scaffold.py` contexts
do), so `| default(false)` is mandatory in all newly-gated and new doc templates.

- `scaffold/mkdocs.yml.jinja`
  - Gate the **whole file** on `has_docs | default(false)` (non-docs products
    emit no `mkdocs.yml` — removes the broken shell).
  - Nav: Home, Getting Started, Architecture, Guides (only the guides that
    exist), API Reference (`reference/` via literate-nav).
  - Plugins: `search`, `gen-files` (`docs/scripts/gen_ref_pages.py`),
    `literate-nav` (`SUMMARY.md`), `mkdocstrings`. **No `section-index`** — the
    reference emits per-module pages only (no `__init__` index pages), so there
    is nothing for it to bind.
  - **mkdocstrings options (verified, spikes 3 + round-2 over the full 14 api +
    401 model modules):** `docstring_style: sphinx`; `filters` excluding `^_`,
    `_with_http_info$`, `_without_preload_content$`, `_serialize$`;
    `show_bases: false` (kills external base-class cross-ref warnings on the 401
    models); `show_docstring_parameters: false` (drops internal
    `_request_timeout`/`_headers` param noise and shrinks the cross-ref surface);
    `paths: ["."]`; `inventories:` for the python + pydantic `objects.inv` so
    remaining annotation refs resolve.
  - Wire `hooks: [docs/_hooks.py]` (the duplicate-param logging filter above) and
    `exclude_docs` so `docs/_hooks.py` + `docs/scripts/` are not copied into the
    built site.
  - Add the **Mermaid** superfences custom fence (mirror phantasos's
    `mkdocs.yml`) — **no extra plugin needed** (verified, spike 2).
- `scaffold/pyproject.toml.jinja`
  - Add a `docs` dependency group (gated): `mkdocs-material`,
    `mkdocstrings[python]>=0.26` (the `inventories:` floor), `mkdocs-gen-files`,
    `mkdocs-literate-nav`. (No `mkdocs-section-index`, no `mkdocs-mermaid2`.)
- `scaffold/noxfile.py.jinja`
  - Add `docs` (`mkdocs build --strict`) and `docs-serve` sessions, gated on
    `has_docs | default(false)`, installing the `docs` group.
- `scaffold/.github/workflows/docs.yml.jinja`
  - This file is wrapped in `{% raw %}…{% endraw %}` (to preserve `${{ … }}`
    GitHub expressions). Place `{% if has_docs | default(false) %}` **before**
    `{% raw %}` and `{% endif %}` **after** `{% endraw %}`. The build step
    already runs `uv run --group docs mkdocs build --strict` — no command change.

## 10. Verification strategy

Per CLAUDE.md (real deps, evidence before assertions, never mock the SUT):

- **Offline unit/behavioral tests** (run in `nox -s gate`): render the docs
  templates with a **real, hand-constructed `OperationInventory` / context** as
  input (legitimate test data, not a mock of the prisma-browser boundary) and
  assert:
  - page set + nav reflect `has_docs` and which guides exist;
  - the CRUD guide contains the real showcase method names and omits absent
    verbs (partial-CRUD degradation);
  - the auth guide lists the credential env vars from `credential_fields()`;
  - non-docs context emits **no** docs files / no `mkdocs.yml`.
- **Integration gate** (new `nox -s docs`, venv-backed, JRE+network like
  `smoke`/`live`; skips cleanly without prerequisites): build the real
  prisma-browser SDK with `docs:` configured, run the real scoped introspect,
  render the site, and run `mkdocs build --strict` in the SDK — proving the
  whole pipeline end to end. Assert the emitted pages contain the real method
  names.
- Existing `gate` (ruff/format/mypy/pytest) and `context` (deep-dive generated
  blocks) must stay green; update `.agents/context/sdk-generator.md` for the new
  stage and run `nox -s context`.

## 11. Spike results (2026-06-18) — all resolved

All five were run against the **real built prisma-browser SDK** before planning.

1. **In-process introspect deps — ✓ RESOLVED.** SDK runtime deps import in the
   phantasos env; scoped `introspect()` returned all 13 resources in-process.
   No subprocess fallback needed.
2. **Mermaid — ✓ RESOLVED.** Renders via Material's `superfences` custom fence;
   **no `mkdocs-mermaid2` needed** (confirmed in a strict build).
3. **mkdocstrings on OAG docstrings — ✓ RESOLVED (the load-bearing finding).**
   The latent `docstring_style: google` is **wrong** — OAG emits **sphinx**
   docstrings. Even with `sphinx` + variant filters, griffe emits benign
   `Duplicate parameter information` warnings (docstring `:param:` vs
   `Annotated[..., Field(description=...)]`) that abort `--strict`, and they are
   **not** suppressible via render options (parse-time). A generated MkDocs
   `hooks:` logging filter drops exactly those records; `mkdocs build --strict`
   then **exits 0** with the reference + mermaid rendered. This keeps both
   decision #1 (autodoc) and #9 (strict).
4. **Verb classification — ✓ RESOLVED.** Real method names are messy
   (`patch_*` for update; `bulk_*`, `by_id`, `by_type_and_id` variants;
   `list_application_categories` is a different noun). The fewest-required-params
   + exclude-`bulk_` + noun-match heuristic picks the right canonical op; a
   `docs.operations` override is the escape hatch. See §7.
5. **adem — ✓ CONFIRMED.** No `docs:` block ⇒ no docs emitted; its current
   broken shell disappears. Acceptable per config-gating.

### Spike round 2 (2026-06-18) — full-tree strict build, post-expert-review

Three expert reviewers stress-tested the plan; two findings invalidated
assumptions and were re-spiked against the **full** reference (14 `api/` + **401
`models/`** modules), not the single-module slice spike 3 used:

- **Cross-reference warnings on the 401 models — RESOLVED.** Predicted autorefs
  "could not find cross-reference target" warnings (from models inheriting
  external `pydantic.BaseModel` etc.) would abort `--strict` and the
  duplicate-param hook wouldn't catch them. Verified fix: `show_bases: false` +
  `inventories:` (python + pydantic) + `show_docstring_parameters: false`. The
  full-tree build then emits **zero** such warnings; `mkdocs build --strict`
  exits 0 with **414 reference pages** rendered.
- **`gen_ref_pages.py` `__init__` handling — RESOLVED.** The naive version emits
  nav leaves literally titled `__init__` and no index pages. Fix: **skip
  `__init__` modules entirely** (per-module pages only); confirmed 0 broken
  pages. This also removes the need for `section-index` and avoids
  re-documenting every re-exported member.
- **`StrictUndefined` gating — RESOLVED.** Bare `{% if has_docs %}` raises on the
  existing scaffold tests; `{% if has_docs | default(false) %}` renders empty.
  Verified empirically.

**Residual polish:** `show_docstring_parameters: false` is now SET (cleaner
reference + fewer cross-refs). Material prints a loud-but-cosmetic "MkDocs 2.0"
banner — not a counted warning; `--strict` is unaffected.

## 12. Affected files (anticipated)

- `src/phantasos/productconfig.py` — `DocsConfig`, `ProductConfig.docs`,
  `has_docs` in context + `_AUTO_EXPOSED`.
- `src/phantasos/generator/sdk/build.py` — docs-introspect stage + context merge.
- `src/phantasos/generator/sdk/docs.py` — **new**: scoped introspect, verb
  classification, `build_docs_context`.
- `src/phantasos/scaffold/docs/**` — **new** page templates, `scripts/gen_ref_pages.py.jinja`,
  and `_hooks.py.jinja` (the strict-build logging filter).
- `src/phantasos/scaffold/{mkdocs.yml,pyproject.toml,noxfile.py}.jinja`,
  `scaffold/.github/workflows/docs.yml.jinja` — gating + docs group + sessions.
- `products/prisma-browser/sdk.yml` — add `docs:` block.
- `noxfile.py` — new `docs` integration session.
- `tests/` — offline docs-rendering tests.
- `.agents/context/sdk-generator.md` — document the docs stage.
- `CHANGELOG.md` — `## [Unreleased]` entry (no version bump on a feature branch).
```
