# Generated CLI: User Config File + Opt-in Pager — Design

**Date:** 2026-06-11
**Status:** Approved design (brainstormed with user; all decisions below are user-confirmed)
**Scope:** phantasos CLI generator (`src/phantasos/generator/cli/`) — emitted into every generated CLI; validated on prisma-browser-cli.
**Driving TODOs:** docs/TODO.md "Pager Output" (primary) and the foundation for "User-Facing CLI Configuration File" (multi-environment — explicitly NOT v1).

## Motivation

The generated CLI has no working user configuration: the emitted `_generated/config.py`
(`resolve()`, path `~/.config/<pkg>/config.yaml`) is dead code — nothing imports it, and
every Typer flag has a hardcoded default. Meanwhile large outputs (e.g.
`show application --all`, thousands of rows) dump straight to the terminal.

This design introduces the first real user-facing configuration file and its first two
consumers: an opt-in auto-threshold pager and the default output format.

## Decisions (user-confirmed)

| Topic | Decision |
|---|---|
| Shipped default | A fully-commented `default_config.yml` ships INSIDE the wheel (`_generated/`); it is the always-present base layer at runtime |
| User override file | `~/.{distribution}/config.yml` (e.g. `~/.prisma-browser-cli/config.yml`) — directory named after the DISTRIBUTION, file named `config.yml` |
| Precedence (per setting) | flag > env (`{ENV_PREFIX}_*`) > homedir file > packaged default |
| v1 schema | Top-level `configuration:` object containing `pager:` and `output:` (see below). Future (NOT v1): top-level `environments:` list (named auth env-var sets) + `configuration.environment` selector |
| Pager engagement | Auto-threshold: page only when rendered output is taller than the terminal AND stdout is a TTY. `--pager`/`--no-pager` per-invocation flags override `enabled` only — threshold + TTY guards always apply |
| Pager mechanism | Rich `Console.pager(styles=True)` with a custom `Pager` subclass; program resolution `configuration.pager.command` > `$PAGER` > `less -RFX`; colors survive |
| Config error policy | Warn + continue, never refuse to run. Unknown keys: warn + ignore. Wrong-typed value: warn + that key falls back to default. Unparseable YAML: warn + whole file ignored |
| Meta commands | `config init [--force]` + `config show`, in a `config` group registered under its own `rich_help_panel="CLI"` (separate from API verb panels in top-level `--help`) |
| Implementation | Approach A: typed pydantic models in the emitted package; config loaded once at app build so Typer defaults (and `--help`) show EFFECTIVE values |

## v1 schema

```yaml
# Shipped default_config.yml (fully commented; comments interpolate the real
# distribution name and env prefix at generation time)
configuration:
  pager:
    enabled: false     # opt-in: page results taller than the terminal
    command: null      # null -> $PAGER -> 'less -RFX'
  output:
    format: json       # json | yaml | table
```

Forward-compatibility: the `configuration:` wrapper exists so `environments:` (a future
top-level sibling list) and `configuration.environment` (a future selector key) can be
added without breaking files. v1 must not implement either.

## Architecture & file map

All new/changed runtime code lives in the emitted `_generated/` (wiped + re-emitted every
build; users never edit it — their state is the homedir file):

```
<pkg>/_generated/
  config.py            REWRITE  typed config: models + load + merge + env + warnings
  default_config.yml   NEW      commented shipped defaults (wheel package data)
  config_commands.py   NEW      `config init` / `config show` Typer sub-app
  output.py            EXTEND   _AutoPager + yaml branch routed through the Console
  runtime.py           EXTEND   pager engagement around result rendering
  app.py               EXTEND   registers the config group (rich_help_panel="CLI")
commands modules       EXTEND   --output default from config; --pager/--no-pager flag
```

Generator side: corresponding `.jinja` templates under
`src/phantasos/generator/cli/templates/_generated/`, `render_cli.py` emission set,
`_CLI_DEPS` += `pydantic>=2.11` (already present transitively via the SDK; made an
honest direct dependency). The wheel ships `default_config.yml` via the same package-data
mechanism that already ships `ir.json`.

## Config module (`_generated/config.py`, rewrite)

### Models

pydantic v2, `extra="allow"` (unknown keys land in `__pydantic_extra__` for warning
collection, never crash):

```python
class PagerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    command: str | None = None

class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    format: str = "json"  # permissive str; values outside json|yaml|table warn

class CliConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow")
    pager: PagerConfig = Field(default_factory=PagerConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

class ConfigFile(BaseModel):
    model_config = ConfigDict(extra="allow")
    configuration: CliConfiguration = Field(default_factory=CliConfiguration)
```

Python field defaults mirror `default_config.yml` exactly. A unit test (emitted into the
CLI's own test suite AND covered by phantasos's fake-SDK tests) locks the two in sync:
loading the packaged YAML must produce a model equal to the all-defaults model.

### Load pipeline

`load_config()` — cached (single read per process), returns the validated model plus a
list of warning strings and the list of sources actually merged:

1. Load packaged `default_config.yml` (importlib.resources). If somehow missing,
   model defaults apply (the models ARE the fallback).
2. If `~/.{distribution}/config.yml` exists: `yaml.safe_load`, deep-merge over the
   packaged layer (dict-recursive; scalars/lists replace).
3. Env overlay. Mapping skips the `configuration` level:
   `{ENV_PREFIX}_PAGER_ENABLED`, `{ENV_PREFIX}_PAGER_COMMAND`,
   `{ENV_PREFIX}_OUTPUT_FORMAT` (prefix = the IR's `env_prefix`, e.g. `PRISMA_BROWSER`).
   Booleans accept `1/true/yes/on` and `0/false/no/off` case-insensitively; anything
   else warns and is ignored.
4. Validate into `ConfigFile`. On a `ValidationError`: warn per offending key (with its
   dotted path), remove those keys from the merged dict, re-validate (key-level
   fallback). On YAML parse error in step 2: warn, ignore the homedir file entirely
   (file-level fallback).
5. Unknown-key warnings: walk `__pydantic_extra__` on every model level and emit one
   warning per unknown key, naming the dotted path and the file.

Warnings print once to stderr at first load. Config loads when `build_generated_app()`
constructs the app — so warnings also surface during `--help`; this is intentional
(a misspelled key is visible immediately).

### Effective defaults in `--help`

Because config resolves before Typer option registration, the emitted `--output` option
uses the resolved value as its Typer default — `--help` shows `[default: table]` when the
user's file says `format: table`, and flag-beats-config falls out of Typer semantics
naturally. The `--pager/--no-pager` flag is tri-state (`bool | None`, default `None`)
and resolves against `cfg.pager.enabled` at runtime.

## Pager (`_generated/output.py` + `runtime.py`)

### Engagement (runtime.run, the single result-rendering choke point)

```python
pager_on = pager_flag if pager_flag is not None else cfg.pager.enabled
if pager_on and sys.stdout.isatty():
    with _console.pager(pager=_AutoPager(_pager_command(cfg)), styles=True):
        output.render(...)
else:
    output.render(...)
```

- Flags override `enabled` only; threshold + TTY guards ALWAYS apply (`--pager` on a
  5-line result prints normally — consistent auto semantics). Piped/redirected stdout
  never pages.
- Errors (stderr console) and `--dry-run` output are never paged.

### `_AutoPager` (Rich `Pager` subclass)

`show(content)` receives the fully rendered ANSI text:
- content line count ≤ terminal height → write directly to stdout (no process spawn);
- taller → `shlex.split` the resolved command, `subprocess.run` with content piped to
  stdin (`shell=False`).
- Resolution order: `cfg.pager.command` > `$PAGER` > `less -RFX`.
- Pager binary missing (`FileNotFoundError`) → warn once, write content directly.
- User quits the pager early (`BrokenPipeError`/SIGPIPE) → swallowed, no traceback.

### Required refactor

The `--output yaml` branch in `render()` currently uses bare `print()`, invisible to
Rich's pager capture. It moves to the module Console (`_console.out(text,
highlight=False)`) — byte-identical output, now capturable. (json/table already render
via `_console`.)

### Flag-name reservation

`pager` joins the injected-option reserved names (`output`, `all`, `verbose`,
`dry-run`); the existing flag-collision caveat (a body/query field with that literal
name) applies unchanged — no new mechanism.

## `config` command group (`_generated/config_commands.py`)

Registered in `app.py` via `app.add_typer(config_app, name="config",
rich_help_panel="CLI")` so top-level `--help` shows API verbs in their usual panel and
`config` in its own "CLI" panel. (The prisma CLI's `configuration` API object —
`request configuration publish` — does not collide: verb-first grammar.)

- **`config init [--force]`** — `mkdir -p ~/.{distribution}/`, byte-copy the packaged
  `default_config.yml` (comments intact) to `config.yml`. If the file exists and no
  `--force`: clear error, non-zero exit. Prints the written path on success.
  Permission failures report the path and exit non-zero.
- **`config show`** — prints the EFFECTIVE merged configuration as YAML, preceded by
  comment lines naming the sources actually merged (packaged defaults, the homedir file
  if loaded, env vars if any applied). Config warnings appear on stderr — `config show`
  works even with a broken file (it shows what is actually in effect), making it the
  "why isn't my setting applying?" debugging tool.

## Generator-side changes

- Templates: rewrite `config.py.jinja`; new `default_config.yml.jinja` (distribution +
  env prefix interpolated into comments) and `config_commands.py.jinja`; extend
  `output.py.jinja`, `runtime.py.jinja`, `commands.py.jinja`, `app.py.jinja`.
- `render_cli.py`: add the new files to the `_generated` emission set. The post-render
  ruff format step only touches `.py` files — `default_config.yml` is exempt by
  construction.
- `_CLI_DEPS` += `pydantic>=2.11`.
- Package data: hatchling ships non-`.py` files inside the package dir (precedent:
  `ir.json`); `default_config.yml` rides the same mechanism. Verified during
  implementation with a wheel-build check.

## Error handling summary

| Failure | Behavior |
|---|---|
| Homedir YAML unparseable | stderr warning; file ignored (defaults + env apply) |
| Unknown config key | stderr warning naming dotted path; key ignored |
| Wrong-typed value | stderr warning; that key falls back to default |
| Bad bool env var | stderr warning; env var ignored |
| Pager binary missing | warn once; output printed directly |
| User quits pager early | SIGPIPE/BrokenPipeError swallowed |
| `config init` target exists | clear error + hint `--force`; exit non-zero |
| `config init` permission error | report path; exit non-zero |

The CLI never refuses to run because of a config problem.

## Testing

1. **phantasos unit/render tests** — emitted files contain the expected structures
   (formatting-robust assertions, per the post-render-ruff note); fake-SDK
   `test_cli_emitted.py` CliRunner coverage: `config init` writes/refuses/`--force`;
   `config show` merges + reports sources; homedir override changes the `--output`
   default (HOME monkeypatched to tmp); env beats file; unknown-key warning on stderr;
   `_AutoPager` unit tests: short content → direct write, tall content → pipes to a
   fake pager (e.g. `cat`), command resolution order, missing-binary fallback.
2. **Defaults-sync lock** — packaged YAML ≡ model defaults (emitted into the generated
   CLI's own test suite via cli-overrides, and exercised in phantasos's fake-SDK build).
3. **Gated real-SDK test** — build the real prisma-browser CLI; CliRunner `config
   init`/`config show` against a tmp HOME. Pager engagement is untestable in CI (no
   TTY); the TTY guard makes never-page the tested non-TTY path, threshold logic is
   unit-tested.

## Out of scope (recorded for later)

- `environments:` list + `configuration.environment` selector (multi-env auth) —
  the schema wrapper exists for it; do NOT implement.
- `config edit` ($EDITOR), auto-setup wizard, history file (separate TODOs).
- Per-product config defaults injected from `cli.yml` (e.g. a product shipping
  `pager.enabled: true`) — natural later extension of the `default_config.yml` template.
- Paging `--help` output (Typer/Click's domain, not result rendering).
