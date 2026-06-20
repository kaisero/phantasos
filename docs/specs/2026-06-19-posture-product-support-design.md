# Posture product support (BPA, Custom Posture Checks) — design

Status: proposed · Date: 2026-06-19 · Branch: `feature/posture-product` (off `develop`)
Spec: `products/posture/openapi.yml` (vendor-provided, **read-only**) — OpenAPI 3.0.3,
9 operations, 2 tags, one core resource (`PostureCheck`).

## 1. Problem & motivation

Add a new product, **posture**, to the phantasos generator and validate the entire
SDK + CLI chain end-to-end against it. Posture is a Palo Alto Networks SCM/Strata
API (Best Practice Assessment config upload + Custom Posture Check lifecycle). It
authenticates with the same SCM OAuth client-credentials flow as prisma-browser and
adem, so the auth component drops in unchanged.

Tracing the spec through the pipeline (`classify.py`, `config.py`, the component
templates) surfaced **three things the current built-ins don't handle**, plus the
usual product-config + non-CRUD mapping work. The user elected to **extend the
framework generically** (rather than posture-specific workarounds), so each gap is
closed with a reusable component/feature that future products inherit.

## 2. Goals / non-goals

**Goals**
- A buildable, importable posture **SDK** (`phantasos sdk build posture`) and a
  working **CLI** (`phantasos cli build posture`).
- Three reusable framework extensions: an **offset/limit pagination** component, a
  **list-style (`_errors[]`) error** component, and **PUT-aware `update_`**
  classification.
- Full posture product config: `sdk.yml`, `hooks.py`, `cli.yml`, `overrides/`,
  `cli_overrides/`.
- Live validation against the real tenant with the existing `~/git/.env`
  (read-path fully; write-path attempted under the Pro-license gate).
- No regressions to prisma-browser / adem (the classifier change is shared).

**Non-goals**
- Editing the vendor spec. `products/posture/openapi.yml` is **read-only**; every
  transform goes through the preprocess pipeline (`hooks.py::preprocess`), exactly
  like adem/prisma-browser.
- Solving the bare-array `list[Model]` request-body introspection gap (posture's
  batch bodies wrap arrays in objects, so they introspect; the bare-array gap is
  out of scope).
- Server-side correctness of the injected illustrative `data` example (the field is
  free-form `additionalProperties: true`; the example is explicitly illustrative).

## 3. Locked decisions (from the grill)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Extend the framework generically** for all three gaps. | Reusable; posture is the motivating case. |
| D2 | **PUT update** → add `("update_", "update", "put")` to `_VERB_PREFIXES`; introduce **`put` sub_verb**; gate the body-optional relaxation to `sub_verb=="patch"` only. PUT keeps required body fields **required**. | Posture's only update is a PUT (full-replace); a partial PUT silently wipes omitted fields. Required body = safe. |
| D3 | **Base URL**: ship default `https://api.strata.paloaltonetworks.com` (spec's "Current" server); `base_url_env=POSTURE_BASE_URL`. | Strata is current; clean per-product override var (cf. adem's `ADEM_BASE_URL`). Live test tries strata first, falls back to sase via `POSTURE_BASE_URL` if needed. |
| D4 | **Full CLI surface.** CRUD on `posture-check`; `request posture-check clone\|batch-upsert\|batch-delete`; `request bpa upload` (initiate); auto `show bpa-result --id`. | User's goal is to exercise the whole pipeline. Batch flags are rough (JSON/scalar) but functional; validated live. |
| D5 | **Vendor spec read-only**; all transforms via `hooks.py::preprocess`. | Stated policy. `tag_operations` can't rename (it only `setdefault`s) → imperative hook. |
| D6 | **Preprocess transforms (all four)**: drop `ExternalTags` (mandatory — fails OAG validation, cf. adem), promote it to root `tags:`, rename `Custom Posture Checks`→`Posture Checks`, inject illustrative create/update body examples. | Tag descriptions + cleaner `client.posture_checks` resource + richer generated examples. |
| D7 | **Include `sdk.yml docs:` showcase block** (mkdocs SDK docs, like prisma-browser). Branch is off `develop` *after* the docs PR (#30) merged, so the machinery is present. | Parity; exercises the docs pipeline too. |
| D8 | **Sequence**: design spec → expert-subagent review → implement → live-validate. | Matches the user's grill→plan→review→implement workflow. |

Mechanical specifics locked here (no further grilling):
- **Object** = `posture-check`; **resource** = `posture_checks` (after the D6 rename).
- **offset pagination** fields: `data_field=data`, `limit_field=limit`,
  `offset_field=offset`, `total_field=total`; stop on a short page **or** `offset≥total`.
- **list_error** fields: `errors_field=_errors`, `message_field=message`,
  `code_field=code`, `request_id_field=_request_id`; iterate, format `code: message`,
  join multiple with `; `.

## 4. Operation → command map (the whole surface)

| operationId | method | SDK (`client.posture_checks.*`) | CLI command | Mechanism |
|---|---|---|---|---|
| `ListPostureChecks` | GET `/v1` | `list_posture_checks` | `show posture-check` (list, paginated) | auto (`list_`) |
| `GetPostureChecksByID` | GET `/v1/{id}` | `get_posture_checks_by_id` | `show posture-check --id` (get) | auto (`get_`, strip `_by_id`) |
| `CreatePostureChecks` | POST `/v1` | `create_posture_checks` | `create posture-check` | auto (`create_`) |
| `UpdatePostureChecksByID` | **PUT** `/v1/{id}` | `update_posture_checks_by_id` | `update posture-check --id` (**put**, body required) | **D2 new** (`update_`) |
| `DeletePostureChecksByID` | DELETE `/v1/{id}` | `delete_posture_checks_by_id` | `delete posture-check --id` | auto (`delete_`) |
| `ClonePostureChecksByID` | POST `/v1/{id}:clone` | `clone_posture_checks_by_id` | `request posture-check clone --id [--name]` | `cli.yml request` |
| `BatchUpsertPostureChecks` | POST `/v1/batch-upsert` | `batch_upsert_posture_checks` | `request posture-check batch-upsert --checks <json>` | `cli.yml request` |
| `BatchDeletePostureChecks` | POST `/v1/batch-delete` | `batch_delete_posture_checks` | `request posture-check batch-delete --ids <...>` | `cli.yml request` |
| `InitiateConfigUpload` | POST `/reports/config-file-upload` | `initiate_config_upload` (resource `config_file_upload`) | `request bpa upload [--delete-after-processing]` | `cli.yml request` |
| `GetBpaResultByID` | GET `/reports/{id}/bpa-result` | `get_bpa_result_by_id` | `show bpa-result --id` (get-by-id-only) | auto (`get_`) |

Notes:
- `_singularize("posture_checks")` → `posture_check`; `_strip_id_suffix` removes
  `_by_id`. Confirmed against `classify.py:39-53`.
- `GetBpaResultByID` is naturally a get-by-id `show` (status poll); kept as `show`
  rather than forced into `request`. The BPA initiate lives in `request` because it
  is a non-CRUD action; the two objects (`bpa`, `bpa-result`) differ but each is
  individually idiomatic.
- Batch ops: posture wraps arrays in objects (`{checks:[…]}`, `{ids:[…]}`), so the
  body model introspects (`introspect.py:90-92`): `ids: list[str]` → `scalar` (single
  `--ids` flag), `checks: list[Model]` → `json` (`--checks` JSON). Rough but usable;
  the bare-array bulk gap (prisma-browser) does **not** apply.

## 5. Framework extension 1 — `offset` pagination component

- **Model** (`src/phantasos/config.py`): `OffsetPagination(_Component)` with
  `data_field="data"`, `limit_field="limit"`, `offset_field="offset"`,
  `total_field="total"`, **`default_page_size: int = 100`** (review A/F2), and
  `template="pagination/offset.py.jinja"`. Register in
  `BUILTIN_PAGINATION = {"cursor": …, "offset": OffsetPagination}`.
- **Template** (`src/phantasos/generator/sdk/components/pagination/offset.py.jinja`):
  a `paginate(list_method, **kwargs)` mirroring the cursor template's signature
  (`runtime.py.jinja:530` calls `list(pg(method, **kwargs))`; `client.py.jinja:43`
  forwards). **Correction (A/F2):** the runtime forwards a query kwarg ONLY when the
  user passed the flag (`runtime.py.jinja:478` skips `None`), so under a bare
  `show posture-check --all`, `kwargs` has **neither** `limit` nor `offset`. The
  template must therefore OWN the defaults, not read them from kwargs:
  - `page_size = kwargs.pop("{{ limit_field }}", {{ default_page_size }})` (explicit
    numeric fallback baked from the model field);
    `offset = kwargs.pop("{{ offset_field }}", 0)`.
  - Loop: call with `{**kwargs, {{ limit_field }}: page_size, {{ offset_field }}: offset}`;
    yield items under `{{ data_field }}`; `offset += len(items)`; **stop** when
    `len(items) < page_size` OR (a `{{ total_field }}` is present and `offset >= total`)
    OR the page yielded nothing. (Drives primarily off the short page; tolerates a
    missing `total`.)
- No CLI-side change: `classify.py:352` already sets `paginated=(sub_verb=="list")`;
  the runtime calls the vendored `paginate()` regardless of strategy (A/F1, F3, F4).

## 6. Framework extension 2 — `list_error` error component

- **Model** (`config.py`): `ListError(_Component)` with `errors_field="_errors"`,
  `message_field="message"`, `code_field="code"`, `request_id_field="_request_id"`,
  `template="errors/list_error.py.jinja"`. Register in `BUILTIN_ERRORS`.
- **Template** (`errors/list_error.py.jinja`): MUST re-export the SAME public surface
  as `nested_error.py.jinja` — `__all__` + all seven typed exceptions
  (`ApiException`, `BadRequestException`, `UnauthorizedException`, `ForbiddenException`,
  `NotFoundException`, `RateLimitException`, `ServiceException`) + `error_message(exc)`
  — because `extras/__init__.py` imports that fixed name list (A/F6; smoke fails
  otherwise). `error_message`: parse the JSON body; read `body[errors_field]` (a list);
  per entry format `f"{code}: {message}"` (or `message` when no code); join with `; `.
  Fall back to top-level `message`/`detail`/`title`, then `exc.reason`. Keep
  `request_id` OUT of the human message (available for a future structured path).
- **CLI diagnostics gap (A/F5 — REQUIRED to close gap #2 at the CLI).** The generated
  CLI does NOT call `error_message()`; it has its own hard-coded body parser,
  `_error_headline` in `templates/_generated/diagnostics.py.jinja`, which probes
  `error`/`message`/`detail`/`title`/`description` + `errorResponse`/`error_response`
  wrappers — it will NOT find posture's `body["_errors"][i]["message"]`, so CLI 4xx
  output would dump raw JSON. **Decision:** extend `_error_headline` with a generic
  list-style probe (if `data.get("_errors")` is a non-empty list of dicts, take the
  first entry's `code`+`message`). This is a generic, low-risk CLI-framework addition
  (benefits any `_errors[]` API), independent of the SDK error component's config.
  - *Known architectural debt (not fixed here):* the SDK error helper is config-driven
    (`errors_field` etc.) while the CLI `_error_headline` is hard-coded — two parsers.
    Unifying them is out of scope; logged for a future cleanup.

## 7. Framework extension 3 — PUT-aware `update_`

- `classify.py`: add `("update_", "update", "put")` to `_VERB_PREFIXES` (order:
  after `create_`, alongside the other simple prefixes; no compound-prefix conflict).
- `ir.py`: add `"put"` to the `SubVerb` Literal (line 46-56). **MANDATORY, not
  cosmetic (A/F8):** `Classification`/`MethodBinding`/`Command` all validate against
  the `SubVerb` Literal, so without `"put"` both `classify_name` and `MethodBinding`
  raise a pydantic `literal_error`. This change must land **with** the classifier
  change. (The pre-existing unused `"update"` member is left alone.)
- **Relaxation gate — POST-LOOP, per-command (A/F10, corrected).** The old
  `classify.py:372` `if verb == "update":` relaxes ALL update body flags. Do NOT gate
  it on the just-appended `binding.sub_verb` inside `_emit` — `cmd.body_flags` is
  command-level (merged across bindings via `_merge_flags`), so a per-binding gate is
  emit-order-sensitive whenever a command merges a `patch` + a `put` binding (the
  fakesdk's `patch_widget`+`update_widget` is exactly this case). **Move the
  relaxation out of `_emit` into the existing post-loop pass** (beside `get_by_id_only`
  / columns, `classify.py:412+`):
  ```
  for cmd in groups.values():
      if cmd.verb == "update" and any(b.sub_verb == "patch" for b in cmd.bindings):
          for f in cmd.body_flags:
              f.required = False
  ```
  → PATCH-capable command ⇒ optional body (partial); **PUT-only command (posture) ⇒
  required body** preserved. Order-independent and correct for the merge case.
- `"put"` must also be added to the two `_SUBVERB_PRIORITY` maps
  (`runtime.py.jinja:227` and `render_cli.py:79`) so it isn't silently the `99`
  fallback (A/F12). Place it just after `patch`. (Harmless for posture's single-PUT
  command, but avoids a latent edge for future patch+put / put-variant products.)
- The `--id required for verb in (update, delete)` block (`classify.py:364`) already
  covers PUT and stays in `_emit` (idempotent per binding). The runtime already
  validates PUT body requireds (`model_construct` is used ONLY for `sub_verb=="patch"`,
  `runtime.py.jinja:328`; PUT falls to validating `model_cls(**parsed)`) — so the IR
  relaxation gate only governs whether the CLI marks flags required for a clean
  "missing flag" message (A/F14).
- **Shared-classifier regression — CONFIRMED SAFE (A/F13)**: prisma-browser's `update_*`
  PUTs are all in `cli.yml hide`/`request`, both of which precede `classify_name`
  (`build_cli_ir:378-384`); `_with_http_info` variants are excluded by
  `introspect._EXCLUDE_SUFFIXES`. adem ships no `cli.yml` (no CLI). Re-build both to
  confirm.

## 8. Posture product config

### 8.1 `products/posture/sdk.yml`
```yaml
package: posture
output: ../../../posture-sdk
base_url: https://api.strata.paloaltonetworks.com
auth:
  type: scm_oauth
  scope_env: SCOPE
  base_url_env: POSTURE_BASE_URL
  config_class_name: PostureConfiguration
pagination: {type: offset}
errors: {type: list_error}
facade: true
hooks: ./hooks.py
docs:
  showcase_resource: posture_checks
  examples:
    create: |
      created = client.posture_checks.create_posture_checks(
          posture_check_create_request=PostureCheckCreateRequest(
              name="Security Rule has logging enabled",
              object_type="security_rule",
              severity="High",
              data={...illustrative rule expression...},
          ),
      )
project:
  distribution: posture-sdk
  description: Python SDK for the Palo Alto Networks Posture Management & Assessment APIs
  author: Oliver Kaiser
  author_email: oliver.kaiser@outlook.com
  repo_url: https://github.com/kaisero/posture-sdk
```
(The exact `showcase_variant`/`examples` keys finalized against the real introspected
model during implementation; `posture_check_create_request` is the OAG body param name.)

### 8.2 `products/posture/hooks.py::preprocess(spec)`
Imperative, in declaration order:
1. Build root `tags:` from `spec["ExternalTags"]` values (title/description), renaming
   `Custom Posture Checks`→`Posture Checks`.
2. Rewrite every operation's `tags: [Custom Posture Checks]` → `[Posture Checks]`.
3. `spec.pop("ExternalTags", None)` (mandatory — else OAG validation fails).
4. Inject named request-body `examples:` into `PostureCheckCreateRequest` /
   `PostureCheckUpdateRequest` content (illustrative `data`).

### 8.3 `products/posture/cli.yml`
```yaml
project: {distribution: posture-cli, …}
request:
  posture_checks.clone_posture_checks_by_id: {object: posture-check, action: clone}
  posture_checks.batch_upsert_posture_checks: {object: posture-check, action: batch-upsert}
  posture_checks.batch_delete_posture_checks: {object: posture-check, action: batch-delete}
  config_file_upload.initiate_config_upload: {object: bpa, action: upload}
columns:
  posture-check: [id, name, object_type, type, severity, management_type]
defaults:
  posture_checks.list_posture_checks: {}   # offset/limit need no sort hack
```
(`bpa-result` columns auto-derive from the get response; `defaults` likely empty —
offset pagination has no cursor-sort quirk like prisma-browser.)

### 8.4 `overrides/` (SDK only — there is NO per-product CLI override)
Mirror prisma-browser's **SDK** overrides: `overrides/README.md.jinja` (mandatory —
`build.py:84-89` raises if absent) and `overrides/tests/`
(`test_models.py.jinja`, `test_sdk_crud_live.py.jinja`). Adapt the CRUD-live test to
posture-check; gate the write-path on Pro-license availability.

**Correction (review B):** there is **no per-product `cli_overrides/` mechanism.** The
CLI build always reads the single framework dir
`src/phantasos/generator/cli/cli_overrides/` (`render_cli.py:22-23`, `cli.py:140`),
whose tests are generic. A `products/posture/cli_overrides/` would be silently inert,
so it is **dropped** from this design. CLI-live coverage is therefore: (a) the emitted
generic CLI smoke/config tests, plus (b) **manual live CLI invocation** during §9
validation (not per-product test files). The minimal REQUIRED posture deliverables are
`sdk.yml`, `openapi.yml` (present), and `overrides/README.md.jinja`; `hooks.py` +
`cli.yml` are required only because this design uses them.

## 9. Verification strategy

1. **Unit/offline** (`uv run nox -s gate`): new tests for `OffsetPagination`,
   `ListError`, and `update_`/`put` classification (incl. body-required-stays-required).
2. **No-regression**: rebuild prisma-browser + adem SDK/CLI; `cli discover` shows no
   newly-unmapped/colliding ops; their gates stay green.
3. **SDK build** (`phantasos sdk build posture`): OAG runs (ExternalTags dropped),
   smoke import passes, facade exposes `posture_checks` + `config_file_upload`.
4. **CLI build** (`phantasos cli build posture`): `cli discover` matches §4 exactly.
   **Treat ANY unmapped op as a hard failure** — `cli.yml` `request:` keys are NOT
   validated against the op index (unlike `defaults`/`columns`; review B), so a typo'd
   resource attr silently falls through to `unmapped` while the build still succeeds.
   Cross-check the four `request` resource attrs (`posture_checks`,
   `config_file_upload`) against the actually-emitted `posture_sdk/api/__init__.py`
   after the SDK build, then confirm `cli discover` reports zero unmapped. Emitted CLI
   must import.
5. **SDK docs** (`uv run nox -s sdk-docs` if wired for posture): strict mkdocs build.
6. **Live** (`uv run nox -s live` / direct, using `~/git/.env`):
   - Read-path: auth handshake, `show posture-check` (list + pagination over real
     predefined checks), `show posture-check --id`, error-handling (`list_error`
     formatting on a forced 4xx).
   - Write-path: attempt `create/update/delete/clone/batch/bpa`; **record actual
     results** — expect `403` (Pro license) on the check mutations; if a Pro license
     is present, run a full create→get→update→delete→clone cycle.
   - Determine the real host (strata vs sase) empirically; set `POSTURE_BASE_URL` if
     strata 404s posture for this tenant.

## 10. Affected files (anticipated)

**Framework (shared):**
- `src/phantasos/config.py` — `OffsetPagination` (incl. `default_page_size`),
  `ListError` + registry entries.
- `src/phantasos/generator/sdk/components/pagination/offset.py.jinja` — new.
- `src/phantasos/generator/sdk/components/errors/list_error.py.jinja` — new.
- `src/phantasos/generator/cli/classify.py` — `update_` prefix; move body-relaxation
  to the post-loop per-command pass.
- `src/phantasos/generator/cli/ir.py` — `put` SubVerb (mandatory).
- `src/phantasos/generator/cli/render_cli.py` — `"put"` in `_SUBVERB_PRIORITY` (~:79).
- `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — `"put"` in
  `_SUBVERB_PRIORITY` (~:227).
- `src/phantasos/generator/cli/templates/_generated/diagnostics.py.jinja` —
  `_error_headline` gains a generic `_errors[]` probe (A/F5).
- Tests (new): `tests/test_config.py` (offset + list_error models), pagination +
  error component render tests, `tests/test_cli_classify.py` (update_/put + PUT-only
  body-required + merged patch+put stays optional).
- Tests (MUST UPDATE — A/F11): `tests/test_cli_classify.py:42-58`
  (`update_device_group` no longer unmapped), `:245-252` (`update:widget` now has
  `{patch, put}` + two bindings); `tests/test_cli_emitted.py:433-449`
  (`test_update_uses_patch` — stale premise/comment; still green by tie-break but
  re-document). None are frozen oracles (`.claude/harness.toml`), so editable.

**Product (posture):**
- `products/posture/sdk.yml`, `hooks.py`, `cli.yml` — new.
- `products/posture/overrides/{README.md.jinja,tests/…}` — new (SDK overrides only).
  (NO `products/posture/cli_overrides/` — that extension point does not exist; review B.)

**Docs/context:**
- `CHANGELOG.md` (`## [Unreleased]`): offset pagination, list_error, PUT update, posture.
- `.agents/context/{components,cli-generator,product-config}.md` — narrative + regen
  (`uv run nox -s context`).

## 11. Open risks

- **Leading-underscore fields** (`_errors`, `_request_id`) in the `Error` schema:
  OAG may alias/mangle these. Response-only, low blast radius; verify at smoke. If it
  breaks generation, add a preprocess rename (`_errors`→`errors`) — but that would
  also change the `list_error` `errors_field`. Decide at build time.
- **`:clone` colon path segment** (`/v1/{id}:clone`): valid URL; OAG keys off
  `operationId`. Verify the generated method + runtime URL templating.
- **PUT relaxation gate** must key off the binding's sub_verb, not the command verb
  (a command can in principle merge patch+put bindings). Posture has only PUT, so
  single-binding; the gate logic still must be binding-scoped for correctness.
- **Pro-license gate** limits live write-path coverage to "attempted + recorded".

## 12. Expert review outcome (2026-06-19)

Two independent reviewers verified this design against the real code before coding.

**Reviewer B (product/CLI mapping) — validated:** resource attrs resolve to
`posture_checks` / `config_file_upload` (so every `cli.yml request`/`docs` key is
correct); all op→command rows in §4 classify as drawn; `docs.showcase_resource`,
`hooks:` field, and preprocess ordering are right. **Corrected:** there is no
per-product `cli_overrides/` (dropped from §8.4/§10); `request:` keys are unvalidated,
so §9 now treats any unmapped op as a hard failure.

## 13. Live validation results (2026-06-19)

Run against the real tenant with `~/git/.env` (scope `tsg_id:1902164213`).

**Surfaced + fixed a real gap the design missed:** the posture vendor spec declares
**no `securitySchemes`/`security`**, so OAG generated methods that never sent
`Authorization` — every call 401'd even with a valid token. Fixed in
`products/posture/hooks.py::preprocess` by injecting a `BearerAuth` (http/bearer)
scheme + a global `security` requirement (same vendor-surgery pattern). Post-fix the
SDK attaches the SCM OAuth token and reaches the API.
*Possible follow-up:* make this generic — when an auth component is configured but the
spec lacks a security scheme, inject one in the build (would prevent this footgun for
any future auth product whose vendor spec omits security).

**Second fix (CLI error UX, surfaced by the actual `posture-cli show posture-check`
e2e):** the SCM authz gateway returns `{"msg": "Access denied"}` on 403, a shape
neither `diagnostics._error_headline` (CLI) nor `list_error.error_message` (SDK)
recognized — so the CLI dumped raw JSON instead of a headline. Added `msg` to both
probes → the CLI now prints `error: 403 Forbidden — Access denied` (verified e2e).

**Verified live (per-endpoint, with `tsg_id:1902164213`):**
- OAuth token issues (valid JWT) and is attached; the SDK reaches posture.
- The account IS authorized for posture **item** operations: `GET /…/{id}`, clone,
  and `show bpa-result --id` all return **404** with the documented
  `{"_errors":[{"message":…}]}` body — which the `list_error` component renders as a
  clean headline ("Posture check not found" / "Task ID not found"). So the
  **`list_error` component is validated live** against real posture error bodies.
- Only the **collection list** `GET /posture/checks/v1` returns **403 "Access
  denied"** — a list-specific authz/license gate (Pro license / RBAC). `create`
  (POST collection) returns 404.
- Cross-check: the SAME token returns **200** for prisma-browser (`/seb-api/v1/*`),
  proving the token + tenant are valid for SCM — the posture-list 403 is a
  per-operation authorization decision, not a token/auth/host/code defect.
- Emitted `overrides/tests/test_sdk_live.py`: `test_get_by_id_reaches_posture`
  **PASSES** (sentinel id → `NotFoundException`, proving auth+reach+error-mapping);
  `test_list_offset_pagination` SKIPS on the list-specific 403. (Both **fail on 401**
  — guarding the security-scheme fix.)

**Blocked (external — IAM):** the full collection **list** + write CRUD round-trip
needs the service account granted posture **list** permission (and the tenant's Pro
license covering it). The frozen CRUD oracle (`test_sdk_crud_live.py`) is therefore
**deliberately not authored** (cannot verify it green); author it once a tenant with
list+write permission exists. The non-frozen `test_sdk_live.py` ships meanwhile and
asserts real behavior (get-by-id reachability) on the current tenant.

## 12. Expert review outcome (2026-06-19)

**Reviewer A (framework) — validated:** offset `paginate()` slots into the runtime
call site; the error component's 8-name public surface is the only smoke contract;
raw-body parsing makes `_errors` aliasing a non-issue; PUT-update is regression-safe
for prisma-browser/adem; `--id`-required + runtime PUT-body validation already exist.
**Corrected:** offset template must own `default_page_size` (runtime passes no
limit/offset when unset, F2); the CLI uses its own `_error_headline`, not
`error_message()`, so closing gap #2 at the CLI needs a `_errors[]` probe in
`diagnostics.py.jinja` (F5); the body-relaxation gate must be a post-loop per-command
pass to be order-independent (F10, highest-risk); `"put"` SubVerb is mandatory (F8)
and belongs in both `_SUBVERB_PRIORITY` maps (F12); three existing tests need updating
(F11). All folded into §5–§7, §9, §10 above.
