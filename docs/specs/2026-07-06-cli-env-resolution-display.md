# Generated-CLI environment resolution: honest `show` + debug logging — design spec

- **Date:** 2026-07-06
- **Branch:** `bugfix/cli-env-handling` (off `develop`) → PR into `develop`, squash, no version bump, `## [Unreleased]`.
- **Status:** Design spec. No code. Precedes a plan.
- **Type:** Bugfix + small UX addition in the **CLI generator** (`src/phantasos/generator/cli/`). No SDK-generator change.
- **Origin:** analysis of a user-reported bug (seen with `prisma-browser-cli`): environment variables correctly override the config file's named-environment values at call time, but `environment show` displays the config-file state, so its output does not match what the CLI will actually use.

---

## 1. Problem

A generated CLI resolves its runtime settings from two layers: a **named-environment file** (`~/.<dist>/environments.yml`) and **environment variables**, with env vars taking precedence. That precedence is correct and stays. The bug is **observability**: the CLI never tells the user when an env var is overriding the file, so:

- **`environment show` lies about the active environment.** It marks the file's `default_environment:` as `(active)` and ignores `<PREFIX>_ENVIRONMENT`. With `PRISMA_BROWSER_ENVIRONMENT=staging` exported, every command runs against `staging` while `environment show` still says `prod (active)`.
- **`environment show` never surfaces per-field overrides.** An exported `CLIENT_ID` silently replaces the stored one; a connection field (e.g. region on prisma-access) is printed as its raw stored value even when an env var overrides it — and stored `${VAR}` references aren't expanded in the display.
- **Nothing is logged.** There is no way to see, even at debug level, which source won for the selection or any field.

### Root cause (verified)

`environment show` and the client read **disjoint** data:

| Concern | What the CLIENT resolves (call time) | What `environment show` reads |
|---|---|---|
| Environment **selection** | `runtime.py:_selected_environment()` — `-e` flag > `<PREFIX>_ENVIRONMENT` > `default_environment()` | `config.default_environment()` — the raw file key only |
| **Credential** fields | `runtime.py:_client()` — `os.environ.get(f.env_var)` **(presence)** overrides `resolve_environment(name)[f.name]` | not shown at all (values are sensitive) — and no *source* either |
| **Connection** fields | `runtime.py:_client()`/`_preflight_connection()` — `os.environ.get(f.env) or resolve_connection(name)[f.env]` **(truthiness)** | `environments.yml` block's raw stored value, no `${VAR}` expansion, no override |

The two paths share only `_raw_environments()`. `config show` is *not* value-broken (its `effective_dict()` already reflects env overrides via `_ENV_MAP`), but it doesn't cover named environments and gives only a coarse `merged from: … environment variables` line — so the fix target is `environment show`, not `config show`.

## 2. Goals / non-goals

**Goals**
- `environment show` reports the **effective** state: the truly-active environment and *why*, and for each field of the active environment, the **source** the value comes from (env var vs stored environment value vs unset) — with secret values never printed.
- One **single source of truth** for resolution, consumed by `_client()`, `_preflight_connection()`, and `environment show`, so display can never drift from behavior again.
- **Debug logging** of resolution: which source won the selection, and each field where an env var displaced a stored value — emitted at `debug` into the existing rotating log; secret *values* never logged (names only).

**Non-goals**
- Changing the precedence itself (env vars still win — desired).
- Reworking `config show` (only a possible later attribution polish; out of scope here).
- Printing credential *values* anywhere (mask preserved).
- A `-e` flag on `environment show` (optional polish; §7).

## 3. Design

### 3.1 Single source of truth — `resolve_effective(name)`

Add one resolver in `config.py` (next to `resolve_environment`/`resolve_connection`, which it subsumes). It returns, per field, the effective value **and** its source, applying the *exact* precedence the client uses today — the three classes keep their distinct semantics (this is load-bearing; a naive uniform merge would change runtime behavior):

```python
# config.py (emitted)
class _Source(str, Enum):        # attribution as DATA, not prose (each consumer renders)
    ENV = "env"                  # a direct exported env var (CLIENT_ID / PANW_REGION)
    STORED = "stored"            # the literal value stored in the environment block
    STORED_REF = "stored_ref"    # a stored `${VAR}` reference, expanded from the env
    DEFAULT = "default"          # a packaged/SDK default fills the gap (e.g. base_url)
    UNSET = "unset"              # nothing anywhere (a required field here is the fix target)

class _EffField(NamedTuple):
    name: str            # credential name ("client_id") or connection env-key
    kind: str            # "credential" | "connection"
    env_var: str         # the overriding env var ("CLIENT_ID", "PANW_REGION")
    client_kwarg: str    # how _client passes it (f.client_kwarg or f.name) — kept so
                         #   _client routes through this without re-reading the IR
    value: str | None    # EFFECTIVE value (None if unset); consumer masks iff secret
    source: _Source      # enum — consumers format their own prose from (source, env_var, name)
    secret: bool

def resolve_effective(name: str | None, *, env: Mapping[str, str] | None = None) -> list[_EffField]:
    """Effective credential + connection fields for environment `name`, applying the
    SAME env-var precedence the client applies, each tagged with its source.

    `env` defaults to `os.environ` — inject a dict to unit-test the precedence as a
    PURE function. Callers must ensure `.env` is loaded first (see the dotenv note).
    The client resolution paths call this too, so display == behavior by construction."""
```

**`.env` parity (load-bearing).** `_client()` calls `load_dotenv(find_dotenv(usecwd=True))` before resolving; `environment show` currently does not, so a `.env`-supplied `CLIENT_ID` would run but not display — the same drift class, via `.env` instead of an exported var. `environment show` (and any standalone `resolve_effective` caller) MUST load dotenv first, exactly as `_client()` does, or the "display == behavior" guarantee is false for the recommended `.env` path.

**Acceptance criterion (the SSoT is only real if the inline copies are deleted):** `_client()` and `_preflight_connection()` MUST be rewritten to consume `resolve_effective` — deleting the inline presence/truthiness override loops at `runtime.py:145-157, 179-181, 97`. If those loops survive, `resolve_effective` is a *fifth* divergent copy and strictly worse than today. The §7 parity test (resolver value == pre-refactor `_client` value, per field) is the guard. `_client` keeps ownership of the required-missing check and the `client_kwarg` remap (using `_EffField.client_kwarg`).

Precedence encoded per class (unchanged behavior):
- **credential** — `os.environ.get(env_var)` is used iff **present** (`is not None`); an exported-but-empty `CLIENT_ID=` wins (and still trips the required check downstream — preserved). Else the stored value, `${VAR}`-expanded.
- **connection** — `os.environ.get(env_var)` used iff **truthy**; empty falls through to the stored value (deliberate — an empty routing header is meaningless).
- **stored `${VAR}` reference** — when the file value itself is `${VAR}`, `_resolve_value` expands it; the source distinguishes this from a direct env override.

`_client()` and `_preflight_connection()` are refactored to consume `resolve_effective` (collapsing the connection or-chain that is currently inlined twice). **No behavior change** — same values, now with a shared, tested path.

### 3.2 Selection fix

Make selection a **single** function `_selected_environment_source() -> tuple[str | None, _SelSource]` returning `(name, source)`, and redefine `_selected_environment()` as `[0]` of it — a *sibling* that re-derives selection is a second copy of the `runtime.py:69-73` precedence (the very duplication that caused this bug). `environment show` reads both name and source from that one function (not `config.default_environment()`). Selection sources: `flag` (`-e`, n/a for `show`), `env` (`<PREFIX>_ENVIRONMENT`), `default` (`default_environment`), `none`.

### 3.3 Debug logging

A module logger `logging.getLogger("<package>.runtime")` (the established `auth_cache` pattern — flows into the rotating JSONL at the configured level; **not** `_diag`, whose `Level` has no DEBUG). Emit inside the shared resolver + selector, so every consumer logs for free:

- `_selected_environment()`: one line naming the winning source, e.g. `selected environment 'staging' (source: env PRISMA_BROWSER_ENVIRONMENT)`.
- `resolve_effective()`: one line **per field whose env var displaced a stored value**, e.g. `client_id: using env CLIENT_ID (overrides environment 'prod')` — **never the value**; for `secret` fields (and, to be safe, all credentials) the value is never logged, only the var name and the fact of override.

The log level knob is the existing `configuration.logging.level` (`debug`/`trace` surface these); default `info` keeps them out of the file until the user opts in.

## 4. User-facing implications (the point of this spec)

### 4.1 `environment show` — new output

**Vocabulary of sources** shown to the user (consistent, short):
- `from env <VAR>` — an exported environment variable is the effective source.
- `from environment '<name>'` — the stored value in the named environment.
- `from environment '<name>' (via ${<VAR>})` — the stored value is a `${VAR}` reference, expanded from the environment.
- `unset` — no value from either layer.
- Active marker gains a reason: `(active — via <PREFIX>_ENVIRONMENT)` or `(active — default_environment)`.

**Before (prisma-browser, `PRISMA_BROWSER_ENVIRONMENT=staging` exported, `CLIENT_ID` exported):**
```
$ prisma-browser-cli environment show
prod (active)
staging
```
*(Wrong: `staging` is what commands actually use, and `CLIENT_ID` is coming from the env, not `prod`.)*

**After** — one aligned `FIELD | VALUE | SOURCE` table for the active environment; **non-secret values are shown** (that is what "what will run" means), **secret values are masked**:
```
$ prisma-browser-cli environment show
prod
staging (active — via PRISMA_BROWSER_ENVIRONMENT)

Active environment 'staging' — effective settings:
  FIELD          VALUE               SOURCE
  client_id      acme-prod-app       env CLIENT_ID (overrides environment 'staging')
  client_secret  ••••• (hidden)      environment 'staging'
  scope          tsg_id:1234...      environment 'staging'
  base_url       (default)           default
```
Rule (one predicate, `_EffField.secret`): **secret** values render `••••• (hidden)`; every other value is shown. The `SOURCE` cell is rendered from the `_Source` enum — `env <VAR>`, `environment '<name>'`, `environment '<name>' (via ${VAR})`, `default`, `unset` — and appends `(overrides environment '<name>')` only when an env var actually displaced a stored value. This aligns credential and connection rows identically (no "some shown, some not" rule).

**Connection-field product (e.g. prisma-access, region overridden by `PANW_REGION`):** the same table, connection fields interleaved:
```
Active environment 'prod' — effective settings:
  FIELD          VALUE               SOURCE
  client_id      acme-prod-app       environment 'prod'
  client_secret  ••••• (hidden)      environment 'prod'
  region         us-east             env PANW_REGION (overrides environment 'prod')
```

**No active environment** (nothing selected, no default): unchanged message —
`no active environment — auth falls back to environment variables` — but now the effective-settings block still shows which env vars *are* providing values, so the user sees the ambient-var state.

### 4.2 Debug log — new output

With `configuration.logging.level: debug` (or `<PREFIX>_LOGGING_LEVEL=debug`), the rotating JSONL log gains lines during any authenticated command:
```
{"level":"DEBUG","logger":"prisma_browser_cli.runtime","msg":"selected environment 'staging' (source: env PRISMA_BROWSER_ENVIRONMENT)"}
{"level":"DEBUG","logger":"prisma_browser_cli.runtime","msg":"client_id: using env CLIENT_ID (overrides environment 'staging')"}
```
Never a token or secret value — variable names and the override fact only. Viewable with `show cli log --level debug` (the log viewer added on the prior branch).

### 4.3 Documentation

- The generated CLI's **Authentication & environments** guide (`docs/guides/authentication.md.jinja`) gains a short "Where settings come from" subsection: the file-vs-env precedence, the `environment show` source column, and how to see it at debug level. This is where a user learns that env vars win *and* how to confirm what's effective.
- CHANGELOG `## [Unreleased]` entry describing the fix + the new source display.

## 5. Config architecture (how it folds in)

- The change is **additive and consolidating**, not a new layer: `resolve_effective` sits beside the existing `resolve_environment`/`resolve_connection` in `config.py` and becomes the one place the file∘env merge with attribution happens; the two older resolvers can be re-expressed on top of it (or kept as thin wrappers) so no caller breaks.
- It respects the established layering — `config.py` owns config knowledge; `runtime.py`/`environment_commands.py` consume it. `environment_commands.py` already imports `runtime` and `config`, so wiring `show` to the shared resolver introduces no import cycle.
- Credential `env_var` is currently absent from `_ENV_FIELDS` (which carries only `{name, secret}`); the resolver needs it — either enrich `_ENV_FIELDS` with `env_var`, or read it from `_ir().credential_fields` (which carries `.env_var`). Enriching `_ENV_FIELDS` keeps `config.py` self-contained; decide at plan time.
- Distinction between **environment selection** override and **per-field** override is preserved end-to-end — they are different mechanisms and the source labels name them differently.

## 6. Edge cases / subtleties (all verified in code)

- **Presence vs truthiness** — credentials use presence (`is not None`), connection + selection use truthiness. `resolve_effective` must encode per-class semantics or `show` will lie in a new way.
- **Exported-but-empty** `CLIENT_ID=` — wins for credentials (presence), shown as `from env CLIENT_ID`, and still fails the downstream required check; empty `<PREFIX>_ENVIRONMENT=` / empty connection var — falls through (truthiness).
- **Stored `${VAR}` reference vs direct override** — both can be in play; sources must distinguish `from env CLIENT_ID` (direct) from `from environment 'prod' (via ${CLIENT_ID})` (stored reference).
- **Masking** — secret credential *values* never printed in `show` or logged; non-secret credential values are also currently not printed by `show` (only source) — keep that (source is the useful new signal; values belong to `config`/the env, not a listing command).
- **No active environment** — `_selected_environment()` returns `None`; `show` must handle a `None` name (effective settings then reflect env-vars-only).

## 7. Testing

Behavioral, through the emitted fakesdk CLI (the `emit_cli(auth=True)` fixture) + the real prisma-browser ring where the field set matters:
- `environment show` marks the env-var-selected environment active with the right reason; falls back to `default_environment` when the var is unset/empty.
- Per-field source: an exported credential var shows `from env <VAR> (overrides …)`; a stored value shows `from environment '<name>'`; a stored `${VAR}` shows the `(via ${VAR})` form; unset shows `unset`/`default`.
- **No secret value** appears in `show` output or in any captured log record (extend the existing `test_token_value_never_logged`-style assertion to env resolution).
- `resolve_effective` parity: the value it returns for each field **equals** what `_client()` builds today (a regression guard that display == behavior) — assert against the pre-refactor resolution.
- Debug logging: with level `debug`, the selection + override lines are emitted (caplog on `<package>.runtime`); at `info` they are not.
- Connection-field product (prisma-access ring or fakesdk-with-connection): effective value + source shown for a region-style field.

## 8. Out of scope

- `config show` per-key attribution (coarse line stays); merging the two "show" surfaces.
- A `-e/--environment` flag on `environment show` to preview a non-active environment (nice future polish; the resolver already takes a `name`).
- Any change to precedence, to the SDK, or to how env vars are consumed.

## 9. Decisions (open questions, resolved by the config-architecture review)

1. **Effective block: active environment only.** The full *name* list shows every environment; the detailed `FIELD | VALUE | SOURCE` block renders for the active one only — a per-env block would misleadingly apply global env-var overrides to inactive envs. (The `-e` preview of a non-active env is a clean future extension; the resolver already takes `name`.)
2. **`resolve_effective` home: enrich `_ENV_FIELDS`** with `env_var` + `client_kwarg` (one more key in the jinja loop, symmetric with `_CONN_FIELDS`'s `{key, env}`). Do NOT read `_ir()` in `config.py` — that module deliberately never imports the IR loader (early-load invariant), and reading it would invert the layering and risk a cycle.
3. **Label form: a real aligned `FIELD | VALUE | SOURCE` table** (§4.1), cells rendered from the `_Source` enum — clearer than prose fragments in a list, and not cryptic like `env:CLIENT_ID`.
4. **Show non-secret values, mask secrets** — "what will run" wants the value; `_EffField.secret` governs masking (`••••• (hidden)`). Uniform for credential and connection rows.

## 10. Review revisions (config-architecture review, folded in)

- **[High] `.env` parity** — `environment show`/`resolve_effective` must load dotenv before resolving (mirrors `_client`); else `.env`-supplied values (the recommended path) display wrong. Added to §3.1.
- **[High] `source` is an enum** (`_Source`), not free-text — attribution is data; each consumer (show, debug log) formats its own prose, so wording can't drift and a future `config show` polish can reuse the vocabulary.
- **[High] one selection function + real consumption** — `_selected_environment` becomes `[0]` of the single `(name, source)` function; `_client`/`_preflight` MUST delete their inline override loops and route through `resolve_effective` (acceptance criterion + parity test), or it's a fifth divergent copy.
- **[Med] `_EffField.client_kwarg`** carried so `_client` remaps without re-reading the IR; `_client` keeps the required-missing check.
- **[Med] pure resolver** — `resolve_effective(name, *, env=None)` takes an injectable mapping so the three precedence rules unit-test as a pure function (dict in), not a monkeypatch dance.
- **[Med] `unset` vs `default` defined** — `default` = a packaged/SDK default fills the gap (legit, e.g. base_url); `unset` = nothing anywhere (and for a *required* credential, the user's fix target). Both map 1:1 to `_Source`.
- **[Low] precedence as a first-class doc artifact** — §4.3's table is canonical, rows map 1:1 to `_Source`, and it states the one surprising asymmetry in a sentence: *an exported credential var always wins, even if empty (then fails the required check); an exported region/environment var wins only when non-empty.*
- **[Low] masking enforced by test** — §7's "no secret in any log record" asserts against the fixture's actual resolved values (secret AND non-secret), and whole-`_EffField` logging/repr is forbidden, so a stray `{value}` in a log line fails the build.
- **[Low] two `show` surfaces kept (principled)** — different files/models/sensitivity; §5 notes a later `config show` attribution polish reuses the same `_Source` enum (cheap convergence, not in this branch's scope).

**Verdict (reviewer):** sound to build once the three HIGH items (dotenv parity, enum source, one-selector + genuine `_client` consumption) are folded — all now in this spec.
