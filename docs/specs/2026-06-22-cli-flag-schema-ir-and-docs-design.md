# CLI flag-schema IR deepening + docs progressive-disclosure — design spec

> Status: **decisions locked (D1–D13) — ready for implementation plan.** Branch `feature/cli-payload-helper`.
> Basis: `docs/research/2026-06-21-cli-payload-helper-ux/`. Scope: deepen the CLI
> `Flag` IR to carry the nested schema of complex (`json`-kind) fields, and render
> that schema in the generated CLI docs site (progressive disclosure). NOT the
> separate `2026-06-19-cli-ir-deepening-design.md` (paginated/leaf/typer_path/columns
> dedup) — different concern.
>
> Decisions are appended as they lock during grilling (D1, D2, …).

## Problem (from research)

Complex body fields (nested object / list / list-of-dict) collapse to `str`/`TEXT`
with empty help and a `'{}'` example. Root cause: the full schema survives
introspection (`FieldInfo.annotation`, `OperationInfo.body_fields`) but is dropped
at `cli/classify.py:fields_to_flags` (the `json` branch sets `py_type="str"`); the
`Flag` IR has nowhere to hold nested structure. Lever: `ir.py`→`spec.py` ships
verbatim to the runtime, so one IR deepening feeds docs + `--help` + runtime.

## Decisions

**D1 — Scope.** This plan covers: (1) deepen the `Flag` IR to carry each
`json`-kind field's nested schema; (2) render that schema in the generated CLI
**docs** site (progressive disclosure); (3) a cheap **`--help` stop-gap** — inject
`[json]` + the nested type into the (today empty) json-flag help, and replace the
`'{}'` synthesized example with a **real skeleton**. Deferred to a follow-up plan:
the `--example`/skeleton flag, the `explain` subcommand, `@file` input, and
schema-aware input errors.

**D2 — IR carries a deduped model registry.** Add `CliIR.models: dict[str,
ModelSchema]` (each model emitted once, keyed by model name). A complex (`json`-kind)
`Flag` references its model **by name** rather than inlining a tree. Rationale:
prisma-browser schemas are deep + reuse-heavy (e.g. `AllowBlockControl` across many
data-control fields), so dedup matters for `ir.json` size and doc readability; maps
1:1 onto the docs "Models section" + anchored-link pattern; references break
cycles/explosion naturally (mirrors pydantic `$defs`/`$ref`).

**D3 — Schema source = pydantic `model_fields` recursion.** Extend the existing
opmodel introspection (which already walks `model_fields` → `FieldInfo` for
top-level body fields) to recurse into nested `BaseModel` annotations / `list[Model]`
/ unions, populating the registry. Reuses `_field_kind`/`_unwrap_optional`/
`_enum_values`; descriptor shape stays ours; no `model_json_schema()` JSON-Schema
impedance. openapi-generator names nested inline objects as real model classes
(→ registry entries); genuinely anonymous `dict`/`Any` shapes are opaque leaves.

**D4 — Two skeleton variants, synthesized from the registry at render time.**
- **Docs (mkdocs): FULL skeleton** — all fields *including optionals*, recursive,
  wire/alias (camelCase) keys, values by `example > default > type-synth`.
- **`--help`: required-only** minimal skeleton (also used as the synthesized example
  value there, replacing `'{}'`).
Both are derived from the `CliIR.models` registry (single source of truth) rather
than stored twice. (Bounding/cycle/oneOf handling → D5.)

**D5 — Bounding + `oneOf`.** Registry/Models tables: each model emitted **once**;
a field pointing to another model renders as an **anchored link** (not inline
re-expansion) → inherently cycle-proof; a `oneOf` field lists **variant refs**
rendered as **tabs**. Full skeleton: recurse, **break cycles** on a model repeated
on the current path (emit `{}`), no hard depth cap; a nested `oneOf` field uses the
**first/showcase variant**. Build-time recursion guard prevents any blow-up.

> Note: D5's "emit once + anchored link" governs the **IR registry** (the deduped
> data store). The **docs rendering** is inline (D6), so it re-expands rather than
> linking to a Models page — the registry stays the normalized source; the docs
> denormalize it inline.

**D6 — Docs rendering = inline per-flag, collapsed.** Each complex flag row in a
command's Body table is followed by a **collapsed-by-default** `pymdownx.details`
block (`???`, not `???+`) holding that model's nested field table. Sub-model fields
become **nested collapsibles** (also collapsed), recursing fully and **cycle-broken**
per D5; `oneOf` fields render as `pymdownx.tabbed` tabs inside the block. No global
Models page (rejected (c)) — maximal locality, matching the research prototype; the
IR registry (D2) still dedups the underlying data. Each command also gets a
collapsed "full body skeleton (copy & fill)" block (the D4 docs skeleton). New
`mkdocs.yml` `markdown_extensions`: `pymdownx.details`, `attr_list`,
`pymdownx.tabbed` (`alternate_style: true`) — `admonition`/`superfences`/
`toc.permalink`/`content.code.copy` are already enabled.

**D7 — Per-field descriptor = CLI-owned `ModelField`/`ModelSchema`** (in `cli/ir.py`),
NOT an extension of the SDK-shared opmodel `FieldInfo` (keeps the SDK introspection
type unpolluted; honors separation-of-duty). Shape:
```python
class ModelField(BaseModel):          # extra="forbid"
    name: str; alias: str             # alias = wire/JSON key — NEW vs FieldInfo
    py_type: str; kind: FlagKind; required: bool
    description: str = ""; enum_values: list[str] | None = None
    default: Any | None = None; example: Any | None = None  # example > default > synth
    model_ref: str | None = None              # nested known model → registry key
    variant_refs: list[str] | None = None     # oneOf/union → variant registry keys (tabs)
class ModelSchema(BaseModel):         # extra="forbid"
    fields: list[ModelField]; is_oneof: bool = False
```
New structural carriers vs today's `FieldInfo`: `alias` (wire keys at render time),
`model_ref`/`variant_refs` (edges that let the registry be walked/linked, not
re-expanded), `example` (data-driven skeleton precedence). `CliIR.models:
dict[str, ModelSchema]`.

**D8 — Recursion runs in the CLI layer, reusing now-public opmodel primitives.**
`build_cli_ir(inv, cfg)` consumes only `FieldInfo` strings (no live-model access);
`cli_operations(package, sdk_path)` (`cli.py:88`) is the one place the live SDK is
imported. Plan: **promote** the 6 walking primitives (`_field_kind`,
`_unwrap_optional`, `_enum_values`, `_scalar_type`, `_model_fields`, `_union_members`
in `opmodel/introspect.py`) to public (or add a public `walk_model(cls)`); a new
**CLI-side `cli/modelschema.py`** drives the recursion where live classes are already
in `sys.modules`, emitting `ModelField`/`ModelSchema` into `CliIR.models` and setting
each json `Flag.model_ref`. **`FieldInfo`/`OperationInfo`/`OperationInventory` stay
untouched**; opmodel changes only by exposing primitives. Rejected (A) recursing
inside opmodel — would force `model_ref`/`variant_refs`/`alias` onto the shared
`FieldInfo` (the pollution D7 rejected) or couple opmodel→`cli/ir.py` (wrong dep
direction). Honors separation-of-duty; price = one extra (cheap, cached) model walk.

**D9 — Minimal skeleton keeps a non-empty guarantee.** When a model has no required
fields, the required-only (`--help` + docs-invocation) skeleton still emits **one
representative field**: the `showcase_variant` for a top-level `oneOf`, else the
**first declared field** (recursing required-only into it). **Validated against the
live `CreateAccessAndDataRuleRequest` model** (real opmodel primitives):
- `--applications` (`AccessAndDataPostApplications`, all-optional): (A) literal →
  `{}` vs (B) guarantee → `{"saas": {"accessMode": "none"}}`.
- `--data-controls` (`AccessAndDataDataControls`, all-optional): (A) `{}` vs (B)
  `{"developerToolsOnWebPages": {"action": "allow"}}`.
- `--access`/`--tracking` (have required fields): (A) == (B) — guarantee never fires.

**Decisive evidence:** `--applications` has `minProperties: 1`, so (A)'s `{}` is an
**invalid** payload (API-rejected) identical to today's broken state; (B) is a valid,
copy-paste-runnable minimal body. **Decision: (B).** Representative-field selection is
NOT configurable (rejected B′) — `showcase_variant` for top-level `oneOf`, else
first-declared. Full docs skeleton (all optionals, D4) is already non-empty, so this
guarantee is specific to the minimal variant.

> **Implementation footnote (added during planning):** the `showcase_variant`-for-
> top-level-`oneOf` sub-clause never reaches the skeleton synthesizer in practice. A
> top-level `oneOf` body is pre-split into per-variant commands (e.g.
> `create:gizmo:simple`), so a body flag's `model_ref` is always a concrete variant,
> never the wrapper. The synthesizer therefore uses **first-declared field** (all-
> optional objects) / **first variant** (nested `oneOf`) and takes no `showcase_variant`
> parameter — equivalent for every real call site.

**D10 — Three rendering surfaces; runtime error example is debug-adaptive.**
1. **Static `--help`** (`commands.py.jinja:18` / `_help_literal`): json-flag help →
   `{f.help} [json: {ModelName}] e.g. {compact-minimal-skeleton}` (single-line,
   compact JSON, registry-driven non-empty minimal).
2. **Docs one-line invocation** (`examples.py:example_value`): replace `'{}'` with the
   single-quoted compact minimal skeleton.
3. **Runtime reactive error example** (`_describe_json_field`/`_skeleton`,
   `runtime.py.jinja:271-306`): today emits required-only **and** only one level deep
   (nested → `None`) — same invalid `{}` for all-optional models. Fix **(b)**: apply
   the non-empty guarantee so the corrective example is a valid minimal body. **NEW
   (user):** when **debug logging is active** show the **FULL** skeleton (all fields
   incl. optionals, recursive) instead. Hook = the existing logging seam, **no new
   `--debug` flag**: `log_level_int(_config.get().logging.level) <= 10` (debug/trace).
   So runtime error example = `full if debug else minimal-non-empty`.

**D11 — Skeleton synthesizer lives in `ir.py`, shipped verbatim to runtime.**
`spec.py` = the entire verbatim text of `ir.py` (`render_cli.py:346-347`), so a
self-contained (stdlib + pydantic only) synthesizer in `ir.py` is available at runtime
via `from .spec import …`. **One** registry-driven implementation (`ModelSchema`/
`ModelField` → JSON): the generator calls it on the just-built registry (docs +
static `--help`); the runtime calls it on deserialized `_ir().models` (error example).
Every surface is byte-identical **by construction**. Split with D8: `cli/modelschema.py`
= "live models → registry"; `ir.py` = "registry → skeleton." Runtime stops walking
live models for skeletons (still imports them for pydantic validation), looking up
`models[flag.model_ref]`; anonymous json (no `model_ref`) keeps today's `{"key":
"value"}` fallback. Intra-CLI drift-free copy (the established mechanism — same as
`CliIR`/`Flag`), NOT the generator/sdk vs generator/cli boundary separation-of-duty
governs. Rejected (B) generator/runtime duplicate (drift risk D10 exists to kill).

**D12 — Test strategy: emitted-package behavioral + synthetic-fixture unit (B).**
Enforced policy: behavioral through the **emitted** package (`tests/test_cli_emitted.py`
`emitted` fixture), real deps, no mocking the SUT, evidence before assertions, gate
stays green. End-to-end gates: emitted `--help` shows `[json: <Model>] e.g. {…}`
(non-empty); emitted docs reference page renders collapsed `details` + `oneOf` tabs +
full-body skeleton and **`mkdocs build --strict` passes**; runtime error example is
debug-adaptive; `CliIR.models` round-trips `model_dump_json`/`model_validate_json`.
Unit edge cases use **small synthetic real-`BaseModel` fixtures** (NOT mocks — real
pydantic inputs to the synthesizer) deliberately exercising all-optional (non-empty
guarantee), nested `oneOf`/union (variant_refs → tabs), `list[Model]`,
`example>default>synth` precedence, and a deliberate **A→B→A cycle** (cycle-break,
which real schemas may never trigger). Rejected (A) real-models-only — leaves the
cycle guard untested.

**D13 — Rollout scope.** **Universal (every generated CLI):** IR deepening
(`CliIR.models`, `Flag.model_ref`, `ModelField`/`ModelSchema`), recursion
(`cli/modelschema.py`), opmodel primitive promotion, synthesizer (`ir.py`), `--help`
stop-gap (`commands.py.jinja`, `examples.py`), debug-adaptive runtime error example.
**Docs-gated (products with a `cli.yml docs:` block):** progressive-disclosure render
(`reference_object.md.jinja` + `mkdocs.yml` extensions) — exactly **prisma-browser**
and **posture** (shared templates → both pick it up). **adem has no `cli.yml`** → no
CLI generated → out of scope. Verify end-to-end on **both**: prisma-browser as the
depth/`oneOf`/all-optional stress case, posture as the simpler smoke.
