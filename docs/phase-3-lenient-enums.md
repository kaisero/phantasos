# Phase 3 — Lenient enums  ✅

## Decision D2
Pydantic v2 honors `Enum._missing_` (verified), so we rebase generated enums onto a
lenient base — the **real value is preserved** (no `enumUnknownDefaultCase` sentinel).

## What was built
`apply_patches.py` writes `prisma_browser/_lenient.py` (`LenientStrEnum`, `LenientIntEnum`,
`UNKNOWN_ENUM_VALUES` registry) and rebases all **124 enum classes** (121 str + 3 int).
`RESOLVE_INLINE_ENUMS=true` makes every enum a named class (no inline validators).

## Acceptance
- Unknown `str` (`scm`) and `int` (`9999`) parse to pseudo-members, are recorded, and
  serialize back to the real value (`json.dumps`/`model_dump_json` → `"scm"`).
- Known values stay canonical; 0 strict enums remain; deterministic.
