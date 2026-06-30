# Restore SCM payload fields (oneOf/anyOf flatten) — Implementation Plan

> **For agentic workers:** implement with the subagent-driven-development flow
> (fresh Opus implementer per task, two-stage spec+quality review after each).
> Steps use `- [ ]`.

**Goal:** A preprocess transform that restores the request-body payload fields that
openapi-generator drops from ~120 SCM schemas, so the generated `prisma_access`
models are constructable — verified by live CRUD.

**Spec:** `docs/specs/2026-06-27-scm-oneof-payload-restore.md` (rev 2 — but see C2 below:
this plan's generalized marker-gate intentionally SUPERSEDES the spec's narrower 109).

---

## Plan rev 2 — review corrections (READ FIRST; authoritative over the steps below)

A python-pro review ran the transform over all 12 real specs. Core approach sound,
**zero over-reach** (skips the 15 real unions + the 2 marker-less mobile-agent schemas).
Required edits, all folded in:

- **C1 — `_leaf_props` yields ALL branch properties, not just `required`** (done in the
  Task-1 code). Without it, `nat-rules` destination-translation (`translated_address`,
  `translated_port`, `dns_rewrite`/`distribution` — multi-field branches, `required:[]`)
  is silently dropped → `NatRules` can't express dest-NAT. `{$ref,title}` branches
  (`dhcp` on layer3-/vlan-interfaces) still yield nothing — a **documented** known
  limitation, not silent.
- **C2 — the fire-count is 119, not 109.** Measured: 119 schemas (108 placement-only +
  11 value-type/membership incl. `addresses`, `address-groups`, `nat-rules`, the
  interfaces, `ipsec-crypto-profiles`, `ospf-auth-profiles`, …). The generalized gate
  ("placement marker present in the reachable leaf set", any oneOf/anyOf depth)
  **supersedes** spec rev 2's "109 / oneOf-only / exact-name-gate" — that was the
  pre-grill scope before G1 (=extend to the 12). Pin **119** in Task 4 Step 2.
  (Mechanism note the reviewer added: the loop is top-level-`components.schemas` only, so
  the 15 cadence/BGP/OSPF unions — which live *nested inside* properties — are never
  visited; the marker-gate is a redundant second safety. `ospf-auth-profiles` IS
  flattened, correctly — it's a real configurable object with `md5`/`password` branches.)
- **C3 — the docs wrapper-rendering suite WILL break and is gate-skipped.** Two tests in
  `tests/test_sdk_docs_wrapper_rendering.py` pin the flattened models as wrappers:
  `test_anyof_wrapper_inlines_payload_and_collapses_container` (asserts `AddressGroups`'s
  page has `Placement:` + inline `Static`/`Dynamic` tables) and
  `test_wrapper_body_synthesizes_constructable_full_nesting` (imports
  `group_type`/`static`/`dynamic`, asserts `AddressGroups(GroupType(Static(`). After
  flatten `AddressGroups` is a plain model and those leaf modules vanish → the first
  fails its asserts, the second `ModuleNotFoundError`s. **These are skipped under `nox -s
  gate`** (need a built prisma-access), so the plan's gate run won't catch them — **Task 4
  Step 5 MUST rewrite/relocate both and explicitly run that suite** (pick a still-anyOf
  model for coverage, or accept reduced anyOf coverage if none remains). These are
  prisma_access's only anyOf-wrapper doc coverage.
- **C4 — `relax_readonly_required` is not "only `id`".** Real `readOnly`+`required` field
  names across the specs: `{id (35), fqdn (1), group (1), log_type (1 — objects:
  auto-tag-actions, in scope), name (2), oid (4)}`. Dropping from `required` (keeping the
  property) is safe for all (a readOnly field must never be required on create; responses
  still type it), but Task 3's audit must EXPECT this set, not assert "only id", and
  confirm `auto-tag-actions.log_type` is safe-to-relax. It runs over all 12 subs — broad
  but defensible; state it.
- **C5 — clean rebuild required** (Task 4 Step 3): the leaf modules
  `folder/snippet/device/group_type/static/dynamic/container_type/address_type` vanish
  after flatten; an incremental build leaves stale `folder.py` + stale imports. Rebuild
  from clean before introspecting.

**Validated right:** CRUD targets real (`TagResource`/`Tags`, `AddressResource`/`Addresses`,
`update_*_by_id` PUT); Task 3 is load-bearing (`addresses`/`address-groups` have `id`
readOnly+required; `tags` does not → `tag` proves the reshape alone); merge-don't-clobber
needed (`zones` `folder` collision); OAG generates the membership case cleanly.

---

## Business intent — validate this before any code

**Who hurts.** A `prisma_access` SDK user cannot create most SCM objects. The generated
body model for ~120 objects (`AntiSpywareProfiles`, `Addresses`, `AddressGroups`,
interfaces, NAT rules, …) is a oneOf/anyOf wrapper that carries **only** the
placement fields (`folder`/`snippet`/`device`) — every real field (`name`, `rules`,
`ip_netmask`, `static`/`dynamic`, …) is absent. Proven: today
`AntiSpywareProfiles(Folder(folder='Shared')).to_dict()` → `{'folder':'Shared'}`; there
is **no way** to put `name`/`rules` in the body. Since the API requires those fields, a
valid create is **impossible through the typed SDK** for these objects.

**Root cause.** The OAS schema is correct — it has the payload in `properties` AND a
sibling `oneOf`/`anyOf` (placement, and for some a value-type union). openapi-generator
cannot represent `properties` + sibling composition, so it generates only the
composition and **silently discards the sibling `properties`** (the payload).

**What we achieve.** A spec-preprocess transform flattens these schemas — merge the
composition's single-field leaves (placement + value-type) into the top-level
`properties` as **optional** fields and drop the composition — so OAG generates a clean
plain model with every real field. The user supplies the payload + one placement (and,
where applicable, one value-type); the API enforces "exactly one" server-side (it
always did — the SDK never usefully enforced it, since the payload was missing). Two
reviews proved the flat body is exactly the wire shape the OAS documents, with **no
serialization-path change** and **zero-code** resource-wrapper/facade ripple.

**Why it matters.** This is the difference between a prisma-access SDK you can build
requests with and one you cannot — for the bulk of SCM objects, including the
most-used `addresses`/`address-groups`. The docs work exposed it; this restores it.

**Done looks like.**
1. `AntiSpywareProfiles`, `Addresses`, `AddressGroups` (and the ~120 family) are plain
   models carrying their real fields; constructing a valid create body is possible.
2. A live create→get→delete round-trip succeeds against the real tenant for a
   representative object (`client.objects.tag`) AND a membership object
   (`client.objects.address`).
3. The 15 genuine discriminated unions (cadence schedules, BGP families, …) are
   **untouched** (no placement marker).
4. The transform fires on a **pinned, test-asserted count**; drift fails the build.

**What this is NOT.** Not preserving the SDK-side "exactly one" type constraint
(relaxed to optional; API enforces it). Not a docs change beyond what follows
naturally (affected models become plain → existing plain-model doc path).

---

## Global Constraints
- Generic + shape-driven; the ONLY hardcoded names are the placement marker
  `{folder, snippet, device}` (the universal SCM "configurable object" signature).
- **Never flatten a schema lacking the placement marker** — that is the guard against
  corrupting the 15 real discriminated unions.
- Merge-don't-clobber; lift each leaf's REAL property schema (keep `pattern`/`maxLength`/
  `description`), never a synthesized bare `string`.
- Emit a `flatten_scm_bodies` build stat; a test pins the exact fire-count.
- No new dependencies. The offline gate (`uv run nox -s gate`) stays green; live CRUD
  via `uv run nox -s live` (skips without creds).

## File structure
- `src/phantasos/generator/sdk/preprocess.py` — **add** `flatten_scm_bodies` (+ a
  `relax_readonly_required` helper, Task 3).
- `src/phantasos/generator/sdk/build.py` — **wire** both into the federated per-sub loop.
- `tests/test_sdk_preprocess.py` — **add** unit tests (synthetic schemas).
- `tests/test_sdk_build.py` — **add** the fire-count assertion + a built-model assertion.
- `products/prisma-access/overrides/tests/` and/or the first-light live test — **extend**
  for the live CRUD round-trip.

---

### Task 1: `flatten_scm_bodies` transform (placement + value-type)

**Files:** Create transform in `preprocess.py`; unit tests in `tests/test_sdk_preprocess.py`.

**Interfaces:** Produces `flatten_scm_bodies(spec, stats)`; consumed by `build.py` (Task 4 wiring).

- [ ] **Step 1: failing unit tests** — a placement-only schema (`{properties:{name},
  oneOf:[{properties:{folder:{type:string,maxLength:64}},required:[folder]}, …snippet,
  …device]}`) flattens to `{name, folder?, snippet?, device?}`, no `oneOf`, `folder`
  keeps `maxLength`; a membership+placement schema (`{properties:{name}, anyOf:[{oneOf:
  [{ip_netmask},{fqdn}]}, {oneOf:[{folder},{snippet},{device}]}]}`) flattens to
  `{name, ip_netmask?, fqdn?, folder?, snippet?, device?}`; a **no-placement** real
  union (`{properties:{x}, oneOf:[{hourly},{daily}]}`) is **left untouched**; a
  collision (`{properties:{folder:{type:string}}, oneOf:[{folder},{snippet},{device}]}`)
  keeps the existing `folder`, adds only `snippet`/`device`.

- [ ] **Step 2: run, watch fail.**

- [ ] **Step 3: implement.**
```python
_PLACEMENT = {"folder", "snippet", "device"}

def _leaf_props(node):
    """Yield (name, property_schema) for every single-field leaf reachable through
    oneOf/anyOf. A leaf is a branch object with exactly one own property (besides the
    placement/required marker)."""
    for key in ("oneOf", "anyOf"):
        for b in (node.get(key) or []):
            if not isinstance(b, dict):
                continue
            if "oneOf" in b or "anyOf" in b:
                yield from _leaf_props(b)
                continue
            props = b.get("properties") or {}
            if props:
                for n, sch in props.items():          # ALL props (multi-field branches: nat-rules dest-NAT)
                    yield n, sch
            else:
                for n in (b.get("required") or []):    # required-only branch
                    yield n, {"type": "string"}
            # KNOWN LIMITATION: a {$ref, title} branch (rare alternative — `dhcp` on
            # layer3-/vlan-interfaces) yields nothing. Document it; do not silently drop.

def flatten_scm_bodies(spec, stats=None):
    schemas = (spec.get("components") or {}).get("schemas") or {}
    for name, s in schemas.items():
        if not isinstance(s, dict) or "properties" not in s:
            continue
        if "oneOf" not in s and "anyOf" not in s:
            continue
        leaves = dict(_leaf_props(s))            # name -> property schema
        if not (_PLACEMENT & set(leaves)):       # GUARD: only configurable SCM objects
            continue
        props = s["properties"]
        for n, sch in leaves.items():
            if n not in props:                   # merge-don't-clobber
                props[n] = sch                   # optional: do NOT add to `required`
        s.pop("oneOf", None)
        s.pop("anyOf", None)
        if stats is not None:
            stats["flatten_scm_bodies"] = stats.get("flatten_scm_bodies", 0) + 1
```
  (Note: the merged leaves are intentionally NOT added to `required` — they are the
  relaxed placement/value-type options.)

- [ ] **Step 4: run unit tests, watch pass.** Confirm the no-placement schema is
  untouched (the corruption guard).

- [ ] **Step 5: commit.**

---

### Task 2: docstring signal + the "exactly one" hint

- [ ] Add to the flattened schema a `description` note (append to existing) — e.g.
  `"Supply exactly one of folder/snippet/device (the configuration container)."` plus,
  when a value-type union was flattened, `"and exactly one value field."` — so the
  human signal lost from the type survives in the docs. Unit-test the description text.
  Commit.

---

### Task 3: relax server-assigned `id` from create-body `required`

**Files:** `preprocess.py` (`relax_readonly_required`); tests.

The flatten faithfully restores `id` (server-assigned, `readOnly`) as `required`, so
`create()` wrongly demands it. The schema is reused for create+response.

- [ ] **Step 1: failing test** — a schema with `required:[id,name]` and `id:
  {readOnly:true}` → after the transform, `id` is NOT in `required` (but stays a
  property, so responses still type it).

- [ ] **Step 2-3: implement** `relax_readonly_required(spec, stats)`: for each component
  schema, drop any `required` entry whose property schema has `readOnly: true`. (Removing
  from `required` only — keep the property — is safe for the shared create/response
  schema: responses still carry `id`; create no longer demands it.) Verify against the
  real specs that the only `readOnly` required fields are server-assigned (`id`, and
  audit any others a scan finds — surface them in the report).

- [ ] **Step 4-5: test pass; commit.**

---

### Task 4: wire in, rebuild, pin the count, and LIVE-verify

**Files:** `build.py`; `tests/test_sdk_build.py`; live test.

- [ ] **Step 1:** wire `flatten_scm_bodies` then `relax_readonly_required` into the
  federated per-sub loop in `build.py` (after `clean`, with `fold_server_prefix`).

- [ ] **Step 2:** `tests/test_sdk_build.py` — assert the build stats fire-count for
  `flatten_scm_bodies` equals the measured total (pin it; the implementer measures it
  on the real specs and hardcodes the number, with a comment — drift then fails).

- [ ] **Step 3:** rebuild prisma-access; assert (built-model introspection) that
  `AntiSpywareProfiles`, `Addresses`, `AddressGroups` are now PLAIN models (no
  `*of_schema_N_validator`) carrying their real fields (`rules`; `ip_netmask`/`fqdn`;
  `static`/`dynamic`) + `folder?/snippet?/device?`, and `id` is not required.

- [ ] **Step 4: LIVE CRUD (the gating proof).** Extend the live suite for a
  create→get→delete round-trip, smallest first:
  - `client.objects.tag` — `create(body=Tags(name="phx-crud-<rand>", folder="Shared"))`
    → `get` → `delete`; log the on-wire body (expect `{name, folder}`, not `{folder}`).
  - `client.objects.address` — a membership object:
    `create(body=Addresses(name="phx-crud-<rand>", ip_netmask="10.0.0.0/24",
    folder="Shared"))` → round-trip. Exercise `replace` (PUT) once (same flat model).
  Run `uv run nox -s live`. A green round-trip on a membership object is the proof the
  reshape is API-accepted. If the API rejects the relaxed shape, STOP and surface —
  the design (D1) changes.

- [ ] **Step 5:** docs ripple — the affected models are no longer wrappers; rebuild docs
  `nox -s sdk-docs --strict` (both products) and confirm they render via the plain-model
  path; update any wrapper-rendering test expectation that referenced these as wrappers
  (the whole-branch review found none asserting a wrapper count, but re-verify). Run
  `nox -s gate`.

- [ ] **Step 6:** `.agents/context` narrative + `nox -s context`; CHANGELOG
  `## [Unreleased]`; commit.

---

## Risks / test plan
- **CRUD rejection** (gating): Task 4 Step 4 live round-trip on `tag` AND `address`
  before declaring done.
- **Over-reach** flattening a real union: the placement-marker guard + the pinned
  fire-count test. Add a unit test that a no-placement `properties`+`oneOf` schema is
  untouched.
- **`id`-relax over-reach**: only `readOnly` fields, only removed from `required`;
  report any non-`id` readOnly-required field found.
- **Multi-field membership branch** (an interface `layer3` whose value is a complex
  object): the leaf is still one named field (`layer3`) whose schema is the complex
  object — merged as one optional property; assert the built model keeps the nested type.
- **Whole-suite**: `nox -s gate` green; built-model assertions; live round-trip.
