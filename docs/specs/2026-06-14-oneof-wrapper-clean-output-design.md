# Clean oneOf wrapper output for generated CLIs — design

**Issue:** _(none yet — bugfix; surfaced via CLI bug analysis 2026-06-14)_
**Status:** approved (grilled + 3-way expert review 2026-06-14)

## Goal

A generated CLI command over a oneOf endpoint (e.g. `prisma-browser-cli show
access-and-data-policy`) must emit a clean payload — the underlying variant
object — not the openapi-generator wrapper scaffolding (`actual_instance`,
`one_of_schemas`, `oneof_schema_*_validator`, `discriminator_value_class_map`)
and not empty `additional_properties: {}` bags. Keep the existing **snake_case**
output contract; do not change the request path or any command's flags/options.

## Problem / current state

`show access-and-data-policy` returns, per `data[]` item:

```json
{ "oneof_schema_1_validator": null, "oneof_schema_2_validator": null,
  "actual_instance": { "id": "...", "type": "Rule", ..., "additional_properties": {} },
  "one_of_schemas": ["Section", "RuleSummary"], "discriminator_value_class_map": {} }
```

Root cause (reproduced against the live SDK):

- The OAS schema `PolicyItem` is `oneOf: [RuleSummary, Section]` + a `type`
  discriminator (`products/prisma-browser/openapi.yml`). openapi-generator's
  Python/pydantic-v2 generator renders this as a **wrapper class**
  (`models/policy_item.py`) whose unwrap logic lives only in a hand-written
  `to_dict()`/`to_json()` — **not** in a pydantic serializer.
- The CLI renderer serializes via `model_dump(mode="json")`
  (`generator/cli/templates/_generated/output.py.jinja:30-31`, `_to_data`).
  pydantic's `model_dump` dumps the wrapper's literal fields, bypassing
  `to_dict()`. So the scaffolding leaks. `additional_properties: {}` is a
  separate, pre-existing artifact (openapi-generator adds the field for
  `additionalProperties:true` schemas; it survives `model_dump`).
- A structural fact constrains the fix: `_to_data` only recurses top-level
  list/dict; once it hits the top-level response model, `model_dump` flattens the
  **entire nested tree in one shot**, so nested `PolicyItem` items never pass back
  through `_to_data`. A per-node fix in `_to_data` therefore cannot fix nested
  wrappers — the unwrap must happen **inside** pydantic serialization.

The SDK model is **not** wrong (`to_dict()` already unwraps). The defect is that
pydantic-native serialization doesn't mirror the generator's `to_dict()`.

Scope: 9 oneOf wrapper models exist; five list-response `show` commands are
affected — `show:{access-and-data,sign-in,security,customization}-policy`
(default columns currently `['one_of_schemas']`) and `show:application` (curated
`actual_instance.*` columns).

## Design

Two generic codegen patches in `src/phantasos/generator/sdk/patches.py` attach
pydantic `model_serializer`s to the generated models at build time, so
`model_dump()`/`model_dump_json()` behave correctly for **every** consumer:

1. **Unwrap (plain serializer) on each oneOf wrapper** — files containing both
   `actual_instance` and `one_of_schemas`:
   ```python
   @model_serializer
   def _phantasos_unwrap(self) -> Any:
       return self.actual_instance
   ```
   Must live on the declared wrapper class (pydantic v2 serializes by declared
   type; a subclass serializer is ignored without `SerializeAsAny`).

2. **Drop-empty-`additional_properties` (wrap serializer) on each model** — files
   containing `additional_properties: Dict[str, Any] = {}` (skipping wrappers):
   ```python
   @model_serializer(mode="wrap")
   def _phantasos_drop_empty_additional_properties(self, handler) -> Any:
       data = handler(self)
       if isinstance(data, dict) and data.get("additional_properties") == {}:
           data.pop("additional_properties")
       return data
   ```

The two target sets are disjoint (wrappers carry no `additional_properties`
field), so no class gets two serializers. Both wire into `apply_generic_patches`
alongside the existing `patch_oneof_first_match`.

Because the CLI renderer already uses `model_dump(mode="json")`,
**`output.py.jinja` needs no change** — clean data falls out automatically.

### Coupled change: column subsystem

The table/column subsystem is coupled to the old scaffolding and **must** change
in lockstep (a forcing function, not a choice): `resolve_columns`
(`generator/cli/columns.py`) raises → build failure on an unknown root field.

- **Introspection** (`generator/cli/introspect.py`): add `_item_fields(item)` and
  use it in `_response_info`'s two returns. For a oneOf list item, report the
  **union (superset)** of the variant models' fields (dedup by name, first-seen
  order) instead of the wrapper scaffolding; otherwise fall back to
  `_model_fields`. Guard member resolution with an `issubclass(BaseModel)` check
  (a variant literally named `List` would resolve to `typing.List` via `getattr`).
- **`products/prisma-browser/cli.yml`**: rewrite curated `application` columns
  from `actual_instance.id` → bare `id`/`name`/`type`/`description`; update the
  explanatory comment.

Confirmed post-fix columns (prototyped against the built SDK): the four policy
commands → `[id, name, type, description, mode, evaluation_order]`;
`show:application` → `[id, name, type, description]`.

### Locked decisions (and rejected alternatives)

1. **Fix locus = SDK `model_serializer` patch.** Rejected: CLI-only post-process
   in `_to_data` (narrower; doesn't fix diagnostics/history/other consumers and
   carries the same column coupling).
2. **oneOf item fields = union/superset.** Rejected: intersection (would fail
   build validation for variant-specific curated columns like `description`).
3. **Keep snake_case** (scaffolding removal only). Rejected: switch to camelCase
   API-parity (breaks every snake_case column/JMESPath selector across all
   commands — a separate redesign).
4. **`additional_properties` = drop-empty-only, preserve non-empty**, via a
   generic SDK wrap-serializer on every model. Rejected: "always drop" (loses
   API-ahead-of-spec data, contradicting the lenient-enum pass-through
   philosophy); CLI post-process location (chose SDK for consistency + to fix all
   `model_dump` consumers).

### Key interactions — verified before approval

- **Composition:** parent wrap → child unwrap → grandchild wrap composes
  recursively; clean nested output, non-empty bags preserved.
- **Context propagation:** `mode` / `by_alias` / `exclude_none` propagate to the
  unwrapped inner instance — so `diagnostics.py` (`model_dump(by_alias=True,
  exclude_none=True)`) still renders camelCase/no-nulls.
- **Request path unchanged:** `to_dict()` calls `model_dump(by_alias=True,
  exclude={"additional_properties"}, exclude_none=True)`; the wrap handler
  respects `exclude=`, so `to_dict()` output is **byte-identical** before/after
  (verified empty + non-empty). Outbound bodies/params serialize via `to_dict()`
  (`api_client.sanitize_for_serialization`), never `model_dump`.
- **Zero pydantic serialization warnings** (1- and 2-member unions, nested +
  standalone).
- **Flags/options unaffected:** generated from `model_fields`/type-hints at build
  time; a serializer changes neither.

## Behavior / invariants

- `show <oneOf-list>` JSON/YAML: flat variant objects, no scaffolding, no empty
  `additional_properties`; snake_case keys (e.g. `evaluation_order`).
- `-o table` for the five commands: real columns resolve and populate (rows
  missing a variant-specific field render empty).
- Non-empty `additional_properties` (undeclared API fields) is preserved.
- Request payloads, dry-run bodies, flags, and `set <obj> <variant>` subcommands
  are unchanged.

## Blast radius

- **Affected consumers:** all `model_dump`/`model_dump_json` on SDK models —
  CLI output (the fix), `diagnostics` error rendering (safe; context propagates),
  history logging (now stores clean dicts; never re-parsed), and `to_str()` debug
  repr. None read the old scaffolding keys; no `model_dump → model_validate`
  round-trip on these models.
- **Cross-product:** `apply_generic_patches` runs for all products. adem gets the
  unwrap serializer (cosmetic in raw JSON; no CLI consumes it) and the drop-empty
  serializer is a no-op (no `additional_properties` fields); `products/scm` is
  unbuildable today, so patches can't reach it. Only prisma-browser's `cli.yml`
  references `actual_instance.*`.
- **Tests:** no frozen oracle (per `.claude/harness.toml` `protected_globs`) is
  affected. `tests/test_cli_emitted_real.py:793-798` (curated column assertion)
  is updated by the plan; in-memory `.actual_instance` attribute tests are
  unaffected.

## Out of scope

- camelCase / API-parity output (separate decision).
- Removing `additional_properties` when non-empty.
- Any change to `output.py.jinja`, request serialization, flags, or new flags.
- Other products' CLIs (no behavioral consumer of the unwrap there today).

## Verification / testing contract

- **Unit (offline):** `tests/test_sdk_patches.py` — patch mechanics (disjoint
  targeting, idempotency) + runtime model_dump behavior on fixtures.
- **Introspection/columns (real SDK):** `tests/test_cli_emitted_real.py` — bare
  `application` columns; a policy command gets real default columns; no
  `one_of_schemas`/`actual_instance`.
- **SDK regression (real SDK):** `tests/test_sdk_oneof_real.py` — model_dump
  unwraps + drops empty bag + preserves non-empty; `to_dict()` byte-identical.
- **Gates:** `uv run nox -s gate` (offline: ruff/mypy/pytest) + `uv run nox -s
  live` (real-tenant CRUD; skips without credentials).
- **Manual evidence:** `prisma-browser-cli show access-and-data-policy` (json +
  `-o table`) shows clean output / populated columns — paste real output before
  claiming success (per the repo test policy).

## Plan / review

Design exploration was completed via `grill-me` (5 decisions resolved) and a
three-way independent expert review (SDK-patch mechanics, introspection/columns,
blast radius — all validated against the built SDK). Implementation plan:
`docs/plans/2026-06-14-oneof-wrapper-clean-output.md`. Implement via
`subagent-driven-development` on `feature/oneof-wrapper-clean-output` (PR `--base
develop`, squash, **no version bump**; record under `## [Unreleased]`). Per the
`.agents/context/` working agreement, read `.agents/context/sdk-generator.md` and
`.agents/context/cli-generator.md` before, and update them + run `uv run nox -s
context` after.
