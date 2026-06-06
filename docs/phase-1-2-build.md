# Phases 1–2 — Build pipeline + codegen patches  ✅

## Phase 1 — Baseline generation + idempotent build
Local pipeline (no Docker): `Makefile` `make build` =
preprocess (`uv` + `ruamel.yaml`) → generate (`java -jar` pinned OAG 7.7.0, `-g python`,
`library=urllib3` [sync], `disallowAdditionalPropertiesIfNotPresent=false`,
`RESOLVE_INLINE_ENUMS=true`) → patch → overlay → smoke.
- Prereqs: JRE 11+ and `uv`. Jar vendored to `.tools/` (gitignored; `make jar` fetches).
- Output: `oag-sdk/prisma_browser` (coexists with the prototype until cutover).
- **Acceptance:** 95 operations; deterministic re-run (stable tree hash).

## Phase 2 — Codegen-bug patches
`apply_patches.py` (idempotent): re-quotes apostrophe enum values
(`'Old McDonald's Farm'` → double-quoted) that OAG emits unescaped.
- **Acceptance:** 420 modules import, 0 failures, no manual edits.
- **Finding (model fidelity):** generator logs 38 non-fatal
  `Required var urls/primaryUrl/mode not in properties` on application-polymorphism
  schemas — no runtime impact on reads (validated Phase 8); write-path audit out of scope.
