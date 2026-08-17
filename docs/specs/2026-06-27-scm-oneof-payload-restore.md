# Restore SCM payload fields lost to openapi-generator's `properties`+`oneOf` collapse

**Status:** reviewed (2× python-pro), corrected to rev 2; pre-grill
**Date:** 2026-06-27

---

## REV 2 — corrected after two python-pro reviews (both GO)

Both reviews validated the root cause and **proved the fix**: one applied the flatten to
`anti-spyware-profiles` and ran real OAG 7.22.0 → a clean `AntiSpywareProfiles` plain
model with all payload fields + `folder?/snippet?/device?`, zero scaffolding. The other
proved CRUD-safety: today's wrapper body serializes to `{folder:'Shared'}` **only** —
name/rules **cannot** be set, so a valid create is *impossible today* for all 109; the
flat body yields exactly the OAS-documented `{name, rules, …, folder}` with **no
serialization-path change**, and the resource-wrapper/facade ripple is **zero-code**
(OAG names the flat model identically; nothing keys on wrapper-ness). **GO.**

**Corrections that bind the implementation:**
- **Count is 109, not 110** (mobile-agent has 0 placement schemas — it was mis-bucketed).
  All 109 are **top-level component schemas, none nested** → iterate `components.schemas`,
  no recursion.
- **Detection MUST name-gate to `{folder,snippet,device}` exactly** (every branch a single
  property whose name ∈ that set). The spec §4 "every branch is a thin single-field object"
  rule is too loose — it would wrongly flatten **15 real discriminated unions** (cadence
  schedules, OSPF auth, BGP families, …). Gate on **`oneOf` only** (placement `anyOf` = 0).
- **Lift the branch's real property schema** (it carries `pattern`, `maxLength:64`,
  `description`), NOT a synthesized bare `type: string`.
- **Merge-don't-clobber the one collision** (`network-services/zones` already has a payload
  `folder` property + a `folder` branch): keep the existing property, add only the missing
  `snippet`/`device`. No `folder_1`.
- **Emit a `flatten_properties_oneof` build stat + a test asserting the exact fire-count**
  (109) — the only mechanical guard against over/under-reach (Risk §6.2).
- D7 (`collapse_allof`): verified non-interacting — none of the 109 sit under `allOf`.
- D5 ripple is verified small: affected models become plain models, render via the existing
  plain-model doc path; no test asserts a wrapper count.

**RESOLVED — D3 was WRONG (now a GRILL fork):** `AddressGroups`/`Addresses` (most-used
objects) do **NOT** retain payload. Verified: `AddressGroups`' reachable leaf fields are
only `{device, dynamic, folder, snippet, static}` — `name`/`description`/`tag` are dropped.
The OAS has them (`properties:[id,name,description,tag]` + `anyOf[oneOf…]`) — same OAG
drop-defect, **different shape** (`properties` + `anyOf[oneOf[sub-wrappers]]`). The 109
placement flatten does NOT fix these; **12 anyOf-wrapper top-level models stay broken**
(objects `addresses`/`address-groups`, the network-services interfaces, `ipsec-crypto-
profiles`, …; plus 2 `mobile-agent forwarding-profile-*` of yet another shape). They need
a second, harder transform.

**GRILL FORKS (the live decisions):**
- **G1 — the 12 anyOf-wrapper models.** Extend this effort to also restore their payload
  (harder: `properties`+`anyOf[oneOf[…]]`), or ship the 109 placement flatten first and
  defer the 12? `addresses`/`address-groups` are among the most-used SCM objects and stay
  unconstructable if deferred.
- **G2 — the `id`-required trap (newly EXPOSED, orthogonal).** Many placement schemas list
  `id` (server-assigned, `readOnly`) in `required`; after flatten the model marks `id`
  required, so `create()` wrongly demands a server-assigned id (and the synthesized example
  shows a bogus `id="example"`). Also relax `readOnly`-required fields out of create-body
  `required` in the same preprocess, or leave it (out of scope)?
- **G3 — live-CRUD first object.** Both reviews say `client.objects.tag` (smallest full-CRUD
  placement object, needs only `[name]`, avoids the id trap) — confirm as the staging proof
  before the 109-wide rollout, and that it exercises PUT/replace too.
- **G4 — the "exactly one placement" human signal** is lost when placement becomes three
  optional fields — a docstring/docs note, or accept server-only enforcement?

---
**Scope:** spec preprocess (`src/phantasos/generator/sdk/preprocess.py`) + federated
build wiring; ripples into the docs wrapper-rendering and the resource wrappers.
**Affects:** the prisma-access SCM specs — **110** request-body schemas across 7
sub-packages (network-services 37, security-services 21, identity-services 19,
objects 16, device-settings 15, config-setup 1, mobile-agent 1).

---

## 1. Problem

~110 SCM object models in the generated `prisma_access` SDK are missing their real
payload fields. Example — `AntiSpywareProfiles`, the body of
`client.security_services.anti_spyware_profile.create(...)`: the generated model is a
`oneOf` of three single-field leaves `Folder{folder}` / `Snippet{snippet}` /
`Device{device}`. The actual profile fields (`rules`, `threat_exception`,
`mica_engine_spyware_enabled`, `name`, `description`, …) are **absent**. A user cannot
construct a valid create body through the typed SDK — the fields aren't there.

This was surfaced by the docs wrapper-rendering work (the docs now faithfully render
the model, making the loss visible) and confirmed by the whole-branch review.

## 2. Root cause (verified)

The OAS schema is NOT lossy — it carries the payload:

```yaml
anti-spyware-profiles:
  type: object
  required: [...]
  properties:                                      # the real payload
    id, name, description, cloud_inline_analysis, …, rules, threat_exception
  oneOf:                                            # the placement constraint
    - {required: [folder]}     # (or properties: {folder})
    - {required: [snippet]}
    - {required: [device]}
```

This is valid JSON Schema: "an object with these properties **AND** matching exactly
one of folder/snippet/device." But **openapi-generator cannot represent a schema that
has both sibling `properties` and `oneOf`** — it generates only the `oneOf` (a wrapper
over the placement branches) and **silently discards the sibling `properties`**. The
payload exists in the spec and is thrown away at generation. 110 schemas hit this.

## 3. Goals / non-goals

**Goals**
- The generated model for each affected schema carries its **full payload** plus the
  placement fields, so a user can construct a valid request body through the SDK.
- Generic + spec-driven (keyed on the schema shape, not per-object names).
- Live CRUD still works against the real tenant for the reshaped bodies.

**Non-goals**
- Preserving openapi-generator's `oneOf` wrapper / the SDK-side "exactly one of
  folder/snippet/device" *type-level* enforcement (the API enforces it server-side;
  SDK-side oneOf wrappers are the very ergonomics problem this removes).
- The anyOf-of-sub-wrappers shape (`AddressGroups = anyOf[ContainerType, GroupType]`,
  which already retains its payload via `GroupType`) — out of scope unless the
  detection proves it's the same defect (see D3).
- Docs rendering changes beyond what naturally follows (affected models become plain
  models → the existing plain-model doc path renders them).

## 4. Proposed design

A preprocess transform `flatten_properties_oneof(spec, stats)` run per-sub in the
federated build (alongside `clean` / `fold_server_prefix`):

For each component schema (recursively, incl. nested) that has BOTH a `properties`
map and a sibling `oneOf` (or `anyOf`) **whose every branch is a thin
single-required-field object** (the SCM placement signature — branch adds exactly one
of `{folder, snippet, device}` and nothing else):
1. **Merge** each branch's field into the schema's top-level `properties` as an
   **optional** property (type `string`), and add nothing to `required`.
2. **Delete** the `oneOf`/`anyOf`.
3. Leave the original `properties`/`required` (the payload) intact.

Result: a plain object schema `{<payload props>, folder?, snippet?, device?}`. OAG
generates a clean pydantic model with every real field. The user supplies the payload
+ exactly one placement field; the API rejects zero/multiple server-side (unchanged
from today's runtime behavior — the SDK never enforced it usefully anyway, since the
payload was missing).

Wire it into `build.py`'s per-sub loop (after `clean`, before/with the other
transforms). Count via `stats`.

## 5. Open design decisions (for the grill)

- **D1 — Relax the oneOf, or preserve "exactly one"?** Recommended: relax to optional
  placement (lose the SDK-side exactly-one type constraint; the API enforces it). The
  alternative (keep a runtime validator) re-introduces wrapper ergonomics. Confirm the
  API accepts the relaxed body shape (D4).
- **D2 — Detection signature precision.** The flatten must fire ONLY on the
  payload+placement shape, never on a legitimate `properties`+`oneOf` that encodes a
  real discriminated union. The scope scan found 110 `properties`+`oneOf` schemas; the
  exact placement-shape sub-count needs a precise, tested signature (every branch is a
  single field in `{folder,snippet,device}`, no other branch content). What about a
  schema whose `oneOf` branches carry MORE than placement? Leave untouched / handle
  separately?
- **D3 — Does this subsume the AddressGroups anyOf shape?** `AddressGroups` retains its
  payload (`GroupType`) and is a different structure (anyOf of two sub-wrappers). Does
  the transform touch it, and should it? (Likely leave it — it's not lossy.) Verify.
- **D4 — CRUD safety (the gating risk).** The reshaped body is a flat object with an
  optional placement field instead of a oneOf. Live-verify a real create/read/delete
  round-trip for ≥1 affected object (e.g. an objects-sub one we have creds for) BEFORE
  rolling out to all 110. If the API rejects the relaxed shape, the design changes.
- **D5 — Docs + resource-wrapper ripple.** Affected models become plain (non-wrapper)
  models → they drop out of the docs wrapper set (Task B) and render via the plain
  path; the resource wrapper's `create(body: <Model>)` type changes from the oneOf
  wrapper to the flat model. Confirm the facade + wrapper classification still hold;
  update the Task-B wrapper-count expectations.
- **D6 — Rollout scope / staging.** All 7 subs at once, or prove it on `objects` first
  (smallest blast radius, live-verifiable) then roll out? 110 schemas is large.
- **D7 — Interaction with `collapse_allof`.** preprocess already has `collapse_allof`;
  ensure the new transform composes (allOf may wrap the properties or the oneOf).

## 6. Risks
- **CRUD breakage** (highest): the relaxed body shape might not be accepted as-is.
  Mitigation: D4 live round-trip before rollout.
- **Over-broad detection** flattening a real discriminated union → wrong model.
  Mitigation: tight, tested signature; report the count flattened per build.
- **OAG still mishandles** the flattened schema (e.g. a property name collision when
  the placement field duplicates an existing property). Mitigation: skip/disambiguate
  on collision; assert generated models gain the payload fields.
- **Docs/wrapper-test churn**: the wrapper set shrinks; update expectations.

## 7. Test plan
- Unit: `flatten_properties_oneof` on a synthetic `properties`+`oneOf-placement`
  schema → flat object with payload + optional placement, no `oneOf`; a real
  discriminated union is left untouched; collision handled.
- Build: rebuild an affected sub; assert the model (e.g. `AntiSpywareProfiles`) now has
  `rules`/`threat_exception`/… fields and is no longer a wrapper.
- **Live CRUD** (D4): a create→read→delete round-trip for an affected object.
- Docs: the affected models render via the plain-model path (no scaffolding); update
  the wrapper-count tests.

## 8. Alternatives considered
- **Merge payload into each oneOf branch** (keep the oneOf, duplicate payload ×3):
  preserves the exactly-one constraint but triples the payload and keeps wrapper
  ergonomics — rejected vs the flat relax.
- **Leave it (docs-only honesty)**: the user explicitly chose to fix the models.
- **OAG config / template patch**: brittle vs a spec-level preprocess; the spec is the
  honest source of the dropped fields.
