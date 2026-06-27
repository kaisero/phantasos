# Backlog — deferred items

Tracked, non-blocking follow-ups deferred from completed work. Each entry has enough
context to pick up cold: **what**, **why deferred**, **where**, and a **suggested fix**.
Newest section first. Remove an item when it lands (reference its commit).

---

## SCM payload-restore (feature: `docs/specs/2026-06-27-scm-oneof-payload-restore.md`, commits `3aa2bda..58afec4`)

### B1. `dhcp` `{$ref, title}` branches are not lifted (2 fields lost)
- **What:** `flatten_scm_bodies` restores all single-field oneOf/anyOf leaves EXCEPT branches
  shaped `{$ref, title}` (no inline `properties`/`required`). The only such case is the
  `dhcp` alternative on `network-services` `layer3-subinterfaces` and `vlan-interfaces` —
  those two models flatten to plain but **cannot configure a DHCP client** (`dhcp` field
  absent). Documented limitation, contained to 2 fields on 2 models.
- **Why deferred:** narrow; the 119-schema bulk is restored and live-proven.
- **Where:** `src/phantasos/generator/sdk/preprocess.py` → `_leaf_props` (the `else` path
  that yields nothing for a `$ref` branch; see the `KNOWN LIMITATION` comment).
- **Fix:** resolve the `$ref` to its target schema and lift its property (or, if the target
  is itself an object, lift the named field). Add a unit test with a `{$ref}` branch +
  rebuild-assert the field appears on `Layer3Subinterfaces`/`VlanInterfaces`.

### B2. `relax_readonly_required` has no fire-count drift guard
- **What:** `flatten_scm_bodies` pins its count (`== 119` in `test_sdk_build.py`), but the
  `readonly_required_relaxed` stat is unasserted — a spec change could silently widen the
  relax surface.
- **Why deferred:** the transform is inherently safe (a readOnly field is never legitimately
  required on create; it only loosens) — cosmetic drift coverage, not a correctness risk.
- **Where:** `tests/test_sdk_build.py` (the `test_full_federation_twelve_subpackages` build
  assertion block) + the stat in `relax_readonly_required`.
- **Fix:** measure the real relaxed-count on a build and pin it like the flatten count.

### B3. `patch_oneof_missing_imports` "already imported" check is a substring
- **What:** the guard `f"import {m}\n" in text` would miss a multi-name import line
  (`from x import A, Number`) and append a harmless duplicate import. OAG emits
  one-import-per-line so it never triggers today.
- **Why deferred:** no real occurrence; the trailing `\n` already guards prefix collisions
  (`Number` vs `NumberRange`).
- **Where:** `src/phantasos/generator/sdk/patches.py` → `patch_oneof_missing_imports`.
- **Fix (only if it ever bites):** word-boundary match within import lines.

---

## SDK docs wrapper-rendering (feature: `docs/specs/2026-06-27-sdk-docs-oneof-wrapper-rendering.md`, commits `9b31ee9..06f6438`)

### B4. ~13 synthesized body examples still non-constructable (UUID-id / regex-string fields)
- **What:** after the `_value` fix (`06f6438`), the remaining non-constructable examples are
  required `str` fields that need a UUID or a regex-pattern value but get `"example"`
  (the `str` category is deliberately left unchanged), plus a `ztna_connector` `\p`
  regex-compile crash that is a model-side bug.
- **Why deferred:** out of the `_value` fix's scope (it targeted dict/object/constrained-int);
  the deep value-fidelity for patterned strings is a separate concern.
- **Where:** `src/phantasos/generator/sdk/examples.py` → `_value` / `_SCALARS`.
- **Fix:** for a `str` field with a `pattern`, synthesize a regex-satisfying sample (e.g. via
  a tiny generator or a curated map); UUID-typed/`format: uuid` fields → a literal UUID. Or
  fall back to opaque `Model(...)` when a required field can't be given a valid value.

### B5. Duplicated container-detection resolvers can drift
- **What:** `examples.py:_is_container` (non-recursive) and
  `gen_ref_pages.py.jinja:_is_container_branch` (recursive via `_leaf_models`) implement the
  same idea two ways (duplicate by design — one runs in the generator, one in the built
  SDK's docs venv). They agree on all current data (containers are one level deep) but would
  disagree on a deeper-nested container.
- **Why deferred:** zero current divergence; SCM payload-restore (B-section above) flattened
  most container wrappers anyway, shrinking the surface.
- **Where:** the two files above.
- **Fix:** add a one-line comment on each noting the intended difference, or align them.

### B6. `gen_ref_pages` "never blank" relies on `actual_instance` being a Union
- **What:** scalar-variant labels come from `actual_instance`'s Union; a hypothetical
  anyOf-of-pure-scalars wrapper (`actual_instance: Any`, no model variants) would yield an
  empty scalar set → a blank page. **0** such wrappers exist today across both SDKs.
- **Where:** `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja`.
- **Fix (if it ever appears):** fall back to `_type_label` on the non-model direct variants
  when the scalar-label set is empty; the `test_scalar_only_wrapper_lists_its_types_never_blank`
  test guards it.

### B7. griffe_pydantic summary block still lists wrapper scaffolding
- **What:** the mkdocstrings member `filters:` suppress the scaffolding *member sections*, but
  the separate griffe_pydantic "Config/Fields/Validators" **summary block** still tooltips
  `anyof_schema_*`/`actual_instance` on wrapper pages (equal on oneOf and anyOf — pre-existing).
- **Why deferred:** it is not governed by `filters:`; suppressing it risks the plain-page
  byte-identity invariant.
- **Where:** `src/phantasos/scaffold/mkdocs.yml.jinja` (filter list) + griffe_pydantic options.
- **Fix:** find a griffe_pydantic option to hide the summary block on wrappers only, or accept
  it; verify plain-model pages stay byte-identical.

---

## Environment / not-code (the user's tenant, not a phantasos defect)

### E1. ztna_connector tenant not onboarded to the ZTNA Connector service
- **What:** every connector endpoint (`connector-images`, `connector-groups`, `tenant:status`,
  `license`) returns `424 tenant (/1902164213) not found`, even with a valid superuser token,
  the correct host (`api.sase`), region (`x-panw-region: americas`), and `x-tsg-id`. The
  connector's own `tenant:status` 424s → the connector micro-service has no record of the
  tenant. The SDK is verified correct end-to-end; this is **connector-side onboarding**.
- **Fix (your side):** onboard tenant `1902164213` to ZTNA Connector (Strata console, or
  `client.ztna_connector` `TenantApi.start_onboarding`). Then the connector endpoints resolve.

### E2. Two pre-existing live `first_light` failures (unrelated to any landed work)
- `network_services` → `400` "Folder Shared doesn't exist" (the test uses `folder="Shared"`,
  valid for objects but not for zones in this tenant) — adjust the test folder or tenant data.
- `ztna_connector` → `424` tenant (same as E1).
- These make `nox -s live` exit 1 even though the SCM CRUD round-trips pass; they reproduce
  independent of recent changes.
