# Migration Plan — `openapi-python-client` → OpenAPI Generator (`python`, Pydantic v2)

Branch: `migrate/openapi-generator-python` (off `prototype`).
Goal: a **native, resource-grouped, Pydantic-based** SDK (`client.<resource>.<op>()`,
typed objects) at **feature parity** with the current prototype, behind an
**idempotent build**. The `prototype` branch (the working openapi-python-client SDK)
stays intact as fallback until cutover.

---

## 1. Why / target architecture

PoC (`/tmp/oag_python`, throwaway) confirmed OpenAPI Generator's `python` generator
produces the desired shape from our **preprocessed** spec:
- **13 resource API classes** (`users_api.py` → `UsersApi.list_users()/get_user_by_id()/…`) vs 95 per-operation files.
- **Pydantic v2 models** (one per schema, camelCase `alias=`, validation, `.model_dump()`).
- **Base URL default** baked into `Configuration` (`https://api.sase.paloaltonetworks.com`).
- Imported cleanly (327 modules, 0 failures) after one codegen-bug patch.

Target package (proposed name `prisma_browser`):
```
prisma_browser/
  api/<tag>_api.py        # one resource class per tag
  models/<schema>.py      # Pydantic v2, one per schema
  api_client.py, configuration.py, rest.py, exceptions.py
  _patches/               # post-gen fixups (apostrophes, lenient enums) — applied by build
  extras/                 # hand-written overlay: auth, retries, pagination, errors, facade
```

---

## 2. Feature-parity matrix (current prototype → target)

| Capability (prototype) | Target approach on OpenAPI Generator | Carries over? |
|---|---|---|
| Spec cleanup (`preprocess_spec.py`) | **Reuse as-is** — generator-agnostic | ✅ reuse |
| 95/95 operations | OAG generates all; verify count parity | ✅ |
| Native models | **Free** (Pydantic v2) | ⬆ upgrade |
| One file per resource | **Free** (`*_api.py` per tag) | ⬆ upgrade |
| Default base URL | **Free** (`Configuration` host) | ⬆ upgrade |
| Lenient enums (`scm`/`cie`/`passkey`) | Re-solve: `enumUnknownDefaultCase` **or** post-gen validator relax + registry | 🔁 rebuild |
| OAuth2 client-credentials (`client_from_env`, `SCOPE`) | Token-provider `Configuration` subclass + `.env` loader | 🔁 rebuild |
| Retries + timeout | urllib3 `Retry` via `Configuration` (status_forcelist, backoff, respect Retry-After) | 🔁 rebuild (simpler) |
| Cursor pagination (`paginate`/`paginate_async`) | Facade-level helper over resource methods | 🔁 rebuild |
| Typed errors (`unwrap`, `ApiException` tree) | Map OAG `ApiException` → typed hierarchy (or thin wrapper) | 🔁 rebuild |
| `client.<resource>.<op>()` ergonomics | **Hand-written facade** binding resources → Api classes | 🔁 new |
| sync **and** async | Decision D1 below | 🔁 decision |
| `cast` collision / mojibake patches | N/A (different tool); OAG has **its own** bugs (apostrophes, …) | 🔁 new patches |
| Idempotent `build.sh` | New pipeline: preprocess → java generate → patch → overlay → smoke | 🔁 rebuild |
| Examples (validate_live, sweep, workflows) | Re-port to new call style | 🔁 rebuild |
| Findings (enum_gaps, policy_403) | Re-point at new SDK; methodology identical | 🔁 rebuild |
| Tests | Build out (was already open) | ➕ new |

---

## 3. Key decisions (resolve at Phase 1 kickoff)

- **D1 — sync vs async.** OAG generates one HTTP library per run (`urllib3` sync *or*
  `asyncio` async), not both like the current SDK. **Recommendation:** ship **sync
  (`urllib3`) first** for parity of breadth; add an async generation later if needed.
  (Confirm whether the modern `python` generator can emit both before committing.)
- **D2 — lenient enums.** **Recommendation:** try `--additional-properties=enumUnknownDefaultCase=true`
  first (maps unknowns to a sentinel, no crash). If it loses the actual value, fall
  back to a post-gen patch that relaxes each `field_validator` to pass-through and
  records the value in a registry (mirrors current `LenientStrEnum`/`UNKNOWN_ENUM_VALUES`).
- **D3 — auth.** OAG `Configuration` exposes `access_token`, read per request. **Recommendation:**
  a `PrismaSaseConfiguration` subclass (or token manager) whose `access_token` property
  lazily fetches/refreshes via the existing client-credentials flow; reuse `SCOPE`/`CLIENT_ID`/`CLIENT_SECRET`.
- **D4 — errors.** **Recommendation:** keep OAG's `ApiException` as the base but add a
  small mapper to the typed hierarchy (`NotFoundError`, `RateLimitedError`, …) for parity.
- **D5 — facade.** A `Client` object exposing `.users`, `.devices`, … each wrapping the
  corresponding `*Api` class, with `paginate`-aware `list` helpers — the pan-scm-sdk feel.

---

## 4. Phased execution (each phase is independently verifiable)

### Phase 0 — Branch & hygiene  ✅ (this commit)
- Branch created; `.DS_Store` ignored/removed; this plan committed.

### Phase 1 — Baseline generation + idempotent build  ✅ DONE
- Local pipeline (no Docker): `Makefile` (`make build`) drives preprocess (uv) →
  generate (`java -jar` pinned OAG 7.7.0, `library=urllib3`, D1=sync) → patch → smoke.
- Jar vendored to `.tools/` (gitignored, `make jar` fetches); JRE 11+ + uv are the only prereqs.
- Output: `oag-sdk/prisma_browser` (coexists with prototype's `prisma-browser-sdk/` until cutover).
- **Acceptance met:** generates; **operations == 95**; **deterministic** (stable tree hash on re-run).

### Phase 2 — Codegen-bug patches  ✅ DONE (import/compile)
- Idempotent `apply_patches.py`: re-quotes apostrophe enum values (`'Old McDonald's Farm'`).
- **Acceptance met:** 420 modules import, 0 failures, no manual edits.
- ⚠️ **Finding (model fidelity, revisit Phase 8):** generator logs 38 non-fatal
  `Required var urls/primaryUrl/mode not in properties` on application-polymorphism
  schemas (`private_application*`, …) — some `allOf`-composed required fields may not
  surface as model attributes. Imports fine; validate against live payloads in Phase 8.

### Phase 3 — Lenient enums (D2)
- Implement chosen approach; add an `UNKNOWN_ENUM_VALUES`-style registry.
- **Acceptance:** parsing `provider="scm"`/`"cie"`, `AuthenticationFactorPinCodeControlMethod="passkey"` does **not** raise; values recorded.

### Phase 4 — Auth (D3)
- `extras/auth.py`: client-credentials token provider + `client_from_env()` (`CLIENT_ID`,
  `CLIENT_SECRET`, `SCOPE`, `PRISMA_SASE_BASE_URL`); auto-refresh before 15-min expiry.
- **Acceptance:** mock-transport tests (token fetch, cache, 401-refresh) pass; live `list_users` 200.

### Phase 5 — Transport, pagination, errors
- Retries/timeout via urllib3 `Retry` (429/5xx, backoff, `Retry-After`).
- `paginate`/`paginate_async` helpers; `unwrap`-equiv + typed `ApiException` mapping.
- **Acceptance:** unit tests for pagination + typed errors; retry on simulated 503.

### Phase 6 — Native facade (D5)
- `extras/facade.py`: `Client` with `.users`, `.devices`, … resource accessors.
- **Acceptance:** `client.users.list()` paginates and returns Pydantic objects.

### Phase 7 — Examples + findings re-port
- Port `validate_live.py`, `sweep_get_endpoints.py` (+ enum-gap accumulation), workflow
  examples, `probe_policy_403.py`, `examples/run.sh` to the new call style.
- **Acceptance:** examples run; `findings/enum_gaps.*` reproduced (≥ the 4 known gaps).

### Phase 8 — Live validation parity
- Run sweep against the entitled tenant; compare endpoint coverage & enum gaps to prototype.
- **Acceptance:** ≥ parity on 200-OK endpoints; **0 deserialization errors**.

### Phase 9 — Tests
- pytest suite: models round-trip, lenient enums, auth flow, pagination, error mapping, facade.
- **Acceptance:** green suite committed under `tests/`.

### Phase 10 — Docs & cutover
- README, `GENERATION_NOTES` equivalent, parity sign-off; decide whether to make this the
  default branch / archive `prototype`.
- **Acceptance:** parity matrix all ✅; stakeholder sign-off.

---

## 5. Risks & mitigations
- **More codegen bugs than the apostrophe one** → Phase 2 sweep compiles *every* module; patches are idempotent and re-applied each build.
- **Pydantic strictness rejecting real payloads** (enums, required fields, `additionalProperties`) → lenient enums (Phase 3) + consider `disallowAdditionalPropertiesIfNotPresent=false`; validate live (Phase 8).
- **Auth refresh semantics differ from httpx.Auth** → isolate in `extras/auth.py` with mock-transport tests.
- **Async parity gap** (D1) → ship sync first; async is additive, not blocking.
- **Java build dependency** → pin jar + JRE; document; keep `prototype` (pure-Python build) until cutover.

## 6. Rollback
`prototype` branch is untouched and fully working. Abort = stay on `prototype`. No cutover
until Phase 10 sign-off.

## 7. Out of scope (this migration)
Write-path validation against live tenant (create/patch rules) — separate, mutating effort.
