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
class _EffField(NamedTuple):
    name: str            # credential name ("client_id") or connection env-key
    kind: str            # "credential" | "connection"
    env_var: str         # the overriding env var ("CLIENT_ID", "PANW_REGION")
    value: str | None    # EFFECTIVE value (None if unset); caller masks if secret
    source: str          # see the source vocabulary below
    secret: bool

def resolve_effective(name: str | None) -> list[_EffField]:
    """Effective credential + connection fields for environment `name`, applying the
    SAME env-var precedence the client applies, each tagged with where it came from.
    The client resolution paths call this too, so display == behavior by construction."""
```

Precedence encoded per class (unchanged behavior):
- **credential** — `os.environ.get(env_var)` is used iff **present** (`is not None`); an exported-but-empty `CLIENT_ID=` wins (and still trips the required check downstream — preserved). Else the stored value, `${VAR}`-expanded.
- **connection** — `os.environ.get(env_var)` used iff **truthy**; empty falls through to the stored value (deliberate — an empty routing header is meaningless).
- **stored `${VAR}` reference** — when the file value itself is `${VAR}`, `_resolve_value` expands it; the source distinguishes this from a direct env override.

`_client()` and `_preflight_connection()` are refactored to consume `resolve_effective` (collapsing the connection or-chain that is currently inlined twice). **No behavior change** — same values, now with a shared, tested path.

### 3.2 Selection fix

`environment show` calls `_rt._selected_environment()` (the real selector), not `config.default_environment()`. To show *why*, expose the selection source — either a sibling `_selected_environment_source() -> tuple[str | None, str]` returning `(name, source)` or fold both into one call. Sources: `flag:-e` (n/a for `show`), `env:<PREFIX>_ENVIRONMENT`, `default_environment`, `none`.

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

**After:**
```
$ prisma-browser-cli environment show
prod
staging (active — via PRISMA_BROWSER_ENVIRONMENT)

Active environment 'staging' — effective settings:
  client_id       from env CLIENT_ID          (overrides environment 'staging')
  client_secret   from environment 'staging'  (secret — value hidden)
  scope           from environment 'staging'
  base_url        default
```
Credential **values are never shown** — only the field, its source, and (for secrets) an explicit "hidden" note. The `(overrides …)` suffix appears only when an env var actually displaced a stored value.

**Connection-field product (e.g. prisma-access, region overridden by `PANW_REGION`):** the effective settings block additionally lists connection fields with their **effective value** (non-secret) + source:
```
Active environment 'prod' — effective settings:
  region   us-east   from env PANW_REGION   (overrides environment 'prod')
  ...
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

## 9. Open questions (for the reviewer / owner)

1. Should the effective-settings block render for **every** listed environment, or only the **active** one? (Spec assumes active-only — least noise, matches "what will run".)
2. `resolve_effective`'s home: enrich `_ENV_FIELDS` with `env_var`, or have the resolver read `_ir().credential_fields`? (Trade: `config.py` self-containment vs. not duplicating the field set.)
3. Source-label wording: `from env CLIENT_ID` vs `env:CLIENT_ID` vs a two-column `SOURCE` table — pick the clearest for non-expert users.
4. Should non-secret credential **values** (e.g. `scope`, `base_url`) be shown in the effective block, or source-only like today? (Spec keeps source-only for consistency and to avoid a subtle "some creds shown, some not" rule.)
