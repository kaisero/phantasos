# Prisma Browser OpenAPI Spec — Enterprise Best-Practices Review

**Spec:** `products/prisma-browser/openapi.yml` (OpenAPI 3.0.0)
**Date:** 2026-06-18
**Scope:** 14,825 lines · 63 paths · ~104 operations · 340 schemas
**Reviewed state:** working tree (includes uncommitted in-progress edits)
**Goal:** improve the spec so phantasos generates high-quality SDK + CLI examples,
and bring it up to enterprise-grade OpenAPI standards.

---

## Bottom line

The hypothesis that **body-level examples are the missing piece is correct.**

The uncommitted work already did the hard schema-hardening — 580 new `description`s,
155 `required`, 113 `enum`, 71 `pattern`, 58 `minLength`, 50 `maxLength`, 53 `nullable`,
36 `readOnly`, 133 new schemas, and `429` wired to a shared response. But:

- **Named `examples:` added = 0**
- Only **1** new scalar `example:` added

Examples are the genuine remaining gap.

**The lever works:** phantasos preserves examples. `src/phantasos/generator/sdk/preprocess.py:14-24`
lists `example`/`examples` as annotation keys it carries through (it only reads them to
classify `allOf` branches; it never strips them). Examples added to the spec propagate to
the generated SDK/CLI.

---

## Current-state metrics

| Signal | Count | Note |
|---|---|---|
| Paths | 63 | |
| Operations | ~104 | all have `summary` (104) |
| Schemas | 340 | |
| Request bodies | 56 | |
| Named `examples:` | **0** | the gap |
| Scalar `example:` | 38 | mostly IDs + response messages |
| Root-level `tags:` block | **0** | 14 tags used, none described |
| `oneOf` | 9 | only 6 have a `discriminator` |
| `discriminator` | 6 | → 3 undiscriminated unions |
| `allOf` | 116 | |
| `nullable` | 184 | OAS 3.0 style |
| `additionalProperties` | 212 | audit free-form vs accidental |
| `readOnly` / `writeOnly` | 36 / 2 | |
| `format: string` (invalid) | 18 | spec bug |
| 401 responses | ~21 / ~104 ops | inconsistent despite global auth |

---

## Tier 1 — Highest leverage for SDK/CLI example quality

### 1. No request-body-level examples
56 request bodies, **0** use the named `examples:` keyword. This is *the* thing that turns
a generated CLI example from `--name string --userIds [...]` into something concrete.

Use the OAS `examples` map (plural, named) on request-body content — supports multiple
scenarios per operation:

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema: { $ref: '#/components/schemas/CreateOrReplaceAppGroupInput' }
      examples:
        minimal:
          summary: Smallest valid group
          value: { name: "Finance apps", applicationIds: ["0AP06GY5P54Q1QN4MKR4AS8GAVRK9"] }
        typical:
          summary: Group with description
          value:
            name: "Finance apps"
            description: "Apps for the finance org"
            applicationIds: ["0AP06...", "0AP07..."]
```

### 2. Property-level `example:` is sparse
Only 38 scalar examples, almost all IDs/messages. Add a representative `example:` to every
meaningful property — especially in **Input/Create** schemas. openapi-generator surfaces
these into model docstrings, and the CLI example / `model-describe` work can synthesize a
full command line when each field carries one.

### 3. No root-level `tags:` block
14 tags are *used* on operations but **none are described**. Add a top-level `tags:` array
with a `description` per tag → becomes the help text for each CLI command group and each SDK
API class. Cheap, high-visibility.

### 4. `operationId` casing is inconsistent
4 are camelCase (`uploadCompanyLogo`, `uploadBrowserIcon`, `uploadBackgroundImage`,
`uploadPacFile`) vs PascalCase everywhere else. These map directly to generated
method/command names. Normalize to `UploadCompanyLogo` etc.

---

## Tier 2 — Enterprise correctness & consistency

### 5. The error model is anemic
`ErrorResponse` is `{error?: string, message: string}` (~line 10139). Enterprise consumers
need machine-parseable errors. Consider RFC 9457 (Problem Details), or at minimum add: a
stable `code` enum, a `requestId`/trace id, and a `details[]` array for field-level
validation errors. This lets the generated CLI's error handling key off `code` instead of
string-matching `message`.

### 6. Error responses are inconsistently wired
Shared `components/responses` exist (`BadRequest`, `Forbidden`, `NotFound`,
`InternalServerError`, `TooManyRequests`) but only `429` reliably `$ref`s them (the in-progress
pass). `400`/`403`/`500` are still **inline-duplicated** across ~97 operations. Finish the
refactor: replace every inline 4xx/5xx with a `$ref`. Also **`401` appears on only ~21 of
~104 operations** despite global `BearerAuth` — every authenticated op can 401, so it should
be on all of them (ideally one shared `Unauthorized` response).

### 7. The shared responses contradict each other
`BadRequest`/`Conflict` wrap the body as `{errorResponse: ErrorResponse}`, but
`Forbidden`/`NotFound`/`InternalServerError` have **no body schema at all**. Pick one
envelope and apply it everywhere, or the generated SDK returns differently-shaped errors per
status code.

### 8. Spec bug: `format: string`
Appears 18× (e.g. `adminComment`, ~line 13278). `string` is not a valid format — `format`
annotates a type (`date-time`, `uuid`, `email`, …). Remove these; some generators warn or
emit junk. (`format: scheme` at 10923 is a false hit — inside a description.)

---

## Tier 3 — Security, metadata, discoverability

### 9. The security scheme is under-documented
Just `http`/`bearer`/`JWT` (line 14821). The SASE platform issues tokens via **OAuth2
client-credentials** (TSG-scoped). Model it as an `oauth2` scheme with the `clientCredentials`
flow, `tokenUrl`, and scopes → the generator can emit an auth helper and accurate auth
examples instead of "bring your own bearer token." (Ties into named-environments /
credential-fields work.)

### 10. Thin `info` + `servers`
`info` has only title/description/version — no `contact`, `license`, `termsOfService`, or
`externalDocs`. `servers` is a single hard-coded URL with no `description` and no **server
variables**, though SASE has regional base URLs. Server variables would let the CLI offer a
region selector instead of a hand-edited base URL.

---

## Tier 4 — Schema modeling that shapes generated types

### 11. Undiscriminated unions
9 `oneOf` but only 6 `discriminator`s → 3 unions with no discriminator. Almost certainly the
source of the "oneOf wrapper scaffolding leaks into CLI `show`" issue. Give every `oneOf` a
`discriminator` with an explicit `mapping` so the generator produces clean typed variants.

### 12. `additionalProperties` 212×
Audit which are intentional free-form maps vs accidental `true`. Unconstrained maps generate
loosely-typed models and weak CLI validation.

### 13. Confirm `readOnly` covers all server-set fields
36 `readOnly`s added — verify `id`, `create_time`, `update_time`, etc. are all marked.
Directly improves CLI example quality: read-only fields are excluded from input models, so
the CLI won't offer `--create-time` flags users can't set, and examples won't include them.

---

## Tier 5 — Optional / modernization

### 14. Consider OpenAPI 3.1
JSON Schema 2020-12: drops `nullable` (184 instances) in favor of `type: [..., 'null']`, adds
the `examples` keyword *inside schemas*, aligns with modern tooling. Larger migration — only
if the phantasos generator chain supports 3.1 cleanly.

---

## Sequencing caveat: fix schemas before authoring examples

The rule-create schemas for **access-and-data / customization / security** policies are known
wrong/incomplete (found via the live e2e suite). Examples are only as good as the schema they
sit on — authoring examples against broken schemas bakes in wrong examples.

**Sequence:** fix those schemas first (seed values straight from passing e2e request bodies),
then add examples.

---

## Suggested next steps

1. **Fix the known-broken policy rule schemas** (prerequisite for trustworthy examples).
2. **Decide the example strategy** — per-operation named `examples` vs property-level
   `example` vs both. Worth grilling before committing.
3. **Redesign the error model** (Tier 2) — high-stakes, also worth grilling.
4. **Finish the shared-response refactor** (400/403/401/500 → `$ref`).
5. **Write an implementation plan** under `docs/plans/` with a verification gate that builds
   the generated CLI and inspects the emitted examples/help.
