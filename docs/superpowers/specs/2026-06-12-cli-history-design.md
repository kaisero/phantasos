# Generated CLI: Command History (WP1 of the Config-File Roadmap) — Design

**Date:** 2026-06-12
**Status:** Approved design (grilled with user; all decisions below user-confirmed)
**Scope:** phantasos CLI generator — emitted into every generated CLI; validated on prisma-browser-cli.
**Roadmap context:** Work package 1 of 3 (History → Logfile → Environments) preparing the
"User-Facing CLI Configuration File" TODO item. Every WP is designed
**config-architecture-first**: each new capability's settings live in the layered config
(packaged defaults ← `~/.{distribution}/config.yml` ← env/.env ← flags), following the
extension recipe this WP also documents in CLAUDE.md.

## Decisions (user-confirmed)

| Topic | Decision |
|---|---|
| Config schema | New `configuration.history:` section — `enabled: true`, `verbose: false`, `file: null`, `max_size_mb: 50` |
| Default state | Recording ON by default (shell-history rationale: valuable before you knew you needed it); metadata-only entries keep it safe |
| `verbose` knob | `false` → metadata-only entry; `true` → entry additionally carries `request_body` and `response_body` (documented sensitivity warning in default_config.yml) |
| Format & location | JSON Lines (one JSON object per line) at `~/.{distribution}/history.jsonl`; `history.file` overrides the path |
| Cap behavior | When the file size ≥ `max_size_mb` (default 50), the CLI prints a stderr warning that the command was NOT recorded and names the remedy (delete the file or raise the cap). NO automatic trimming. One warning per invocation (one-shot process) |
| Clearing | v1: manual file deletion (the cap warning says exactly that). No clear command |
| Entry identity | Monotonic integer `id` (last entry's id + 1; starts at 1; restarts after manual clear). `show cli history --entry <id>` addresses entries |
| Recorded scope | **Real API calls only**: every `runtime.run()` invocation that actually calls the SDK. `--dry-run` rehearsals leave NO trace; meta commands (`config …`, `show cli …`, `--help`) are never recorded |
| Failure policy | History writing is best-effort: any I/O problem warns on stderr and the command continues unharmed (consistent with the config layer's warn-and-continue) |
| Read side | `show cli history` — table BY DEFAULT (columns: id, date, command, status), chronological (oldest→newest), last 20 entries by default, `--limit N` overrides (`--limit 0` = all), pager-integrated (`maybe_paged`). `--entry <id>` prints that entry as Rich JSON (incl. bodies when recorded). The TODO's `--verbose` list flag is SUPERSEDED (table is now the default view; full detail lives behind `--entry`) |
| Command grammar | `cli` is a static meta-OBJECT under the `show` verb (future home of `status`, `changelog`; `request cli …` later). Build-time guard: if the classifier ever produces an API object named `cli`, `cli build` fails with a clear error |
| `.env` harmony fix | `load_dotenv(find_dotenv(usecwd=True))` moves to the TOP of `load_config()` (guarded import, like `_client()`'s existing call which stays — idempotent). `.env`-declared `{PREFIX}_*` variables now reach the config layer for EVERY option (pager, output, history, future) |
| CLAUDE.md | Created on this branch: verbatim base = the `worktree-harness-thin-slice` branch's CLAUDE.md (agent working agreement) + a new "Adding a CLI configuration option" recipe section (so the eventual branch merge concatenates instead of conflicting) |

## History entry schema

```json
{"id": 42,
 "ts": "2026-06-12T09:14:02Z",
 "command": "delete device-group --id DG1",
 "sdk_method": "device_groups.delete_device_group",
 "status": "error",
 "http_status": 404,
 "error": "device group not found",
 "duration_ms": 412}
```

- `command`: reconstructed from `sys.argv[1:]` (program name dropped) — exactly what the
  user typed after the binary. Auth never appears (credentials come from env/.env).
- `status`: `"success" | "error"`. On SUCCESS the SDK returns parsed models — no HTTP
  status code is available — so success implies 2xx and `http_status` is OMITTED;
  on error it comes from the `ApiException`. `error` carries the same best-effort
  headline `render_error` shows.
- `duration_ms`: wall time of the SDK call.
- With `history.verbose: true`, two additional fields: `request_body` (the built body
  model, dumped) and `response_body` (the result, dumped via the output module's
  `_to_data`-style conversion). Bodies count toward the 50 MB cap naturally.
- ~~Conscious v1 trim: NO request method/URL field~~ — SUPERSEDED same-day (see the
  "http_method / http_uri" addendum below): the trim's `_serialize`-cost rationale
  turned out to be avoidable, and the user requested the fields by default.

### id assignment & concurrency

`id` = the last line's `id` + 1, read by scanning the file tail (corrupt/non-JSON last
line → scan back a few lines; empty/missing file → 1). Appends are single-line
`O_APPEND` writes. Two concurrent CLI processes can race the id read — accepted and
documented (worst case: duplicate id, both entries preserved; `--entry` returns the
first match).

## Recording mechanics

The single choke point is `runtime.run()`:

- After a successful SDK call (and `after_call` hook): append a success entry, then
  render. After a failed call (the existing `except` branch): append an error entry,
  then render the error as today.
- `dry_run` returns before any recording. Meta commands never enter `runtime.run()`.
- The writer lives in the emitted `_generated/history.py` (new module): owns entry
  construction, id assignment, cap check + warning, append, and the read API used by
  `show cli history` (`read_entries(limit)`, `read_entry(id)` — skipping corrupt lines
  with a stderr note).

## `show cli history` (emitted `_generated/cli_commands.py`, new)

A static Typer sub-app registered in `build_generated_app` as
`verb_apps["show"].add_typer(cli_show_app, name="cli")`.

```
$ pb show cli history                  # table: id | date | command | status (last 20)
$ pb show cli history --limit 0        # everything
$ pb show cli history --entry 42       # the full JSON entry (bodies if recorded)
```

- Table rendering via the output module's Console (so `maybe_paged` integration works
  exactly like API output; honors `configuration.pager`).
- `--entry` prints Rich JSON to stdout; exit 1 with a clear message for an unknown id.
- History disabled + empty/missing file → friendly empty-state message, exit 0.

### Reserved object guard

`render_cli` (or `cli build`) fails the build with a clear message if the IR contains a
command whose object segment is `cli` — the name is reserved for the meta-object across
ALL verbs (future: `show cli status`, `request cli environment`).

## Config-architecture changes (the recipe in action)

1. `config.py.jinja`: `HistoryConfig` model (frozen, extra="allow") — `enabled: bool = True`,
   `verbose: bool = False`, `file: str | None = None`, `max_size_mb: int = 50`; field on
   `CliConfiguration`; `effective_dict()` gains the section.
2. `default_config.yml.jinja`: commented `history:` block incl. the verbose-sensitivity
   warning and env-var reference lines.
3. `_ENV_MAP` + `_BOOL_PATHS`: `{PREFIX}_HISTORY_ENABLED` (bool), `{PREFIX}_HISTORY_VERBOSE`
   (bool), `{PREFIX}_HISTORY_FILE`, `{PREFIX}_HISTORY_MAX_SIZE_MB` (int via pydantic lax
   coercion — numeric strings validate; garbage warns through the loc-removal path).
4. `.env` fix: `load_config()` starts with the guarded `load_dotenv(find_dotenv(usecwd=True))`.
5. The existing defaults-sync test (packaged YAML ≡ model defaults) covers the new
   section automatically; `config show` displays it via `effective_dict`.

## CLAUDE.md (created at repo root on this branch)

Base content: the `worktree-harness-thin-slice` CLAUDE.md verbatim (test policy +
environment notes). Appended section: **"Adding a CLI configuration option"** — the
canonical checklist:

1. Field on the right section model in `config.py.jinja` (frozen pydantic; new sections
   are their own `XxxConfig` model with `Field(default_factory=…)`).
2. Commented entry in `default_config.yml.jinja` (defaults MUST mirror the model — the
   defaults-sync test enforces it).
3. `_ENV_MAP` row using the `{PREFIX}_{SECTION}_{KEY}` naming rule (+ `_BOOL_PATHS` for
   booleans; ints ride pydantic lax coercion).
4. `effective_dict()` extension (drives `config show`).
5. Behavioral tests through the emitted package (HOME/env set BEFORE import; the
   `emitted` fixture's sys.modules purge resets the cache).
6. Settings flow identically from: packaged default → homedir config.yml → `.env` /
   shell env → (where applicable) per-invocation flag. Document the option everywhere
   a user looks: default_config.yml comments are the user-facing reference.

## Error handling summary

| Failure | Behavior |
|---|---|
| History file at/over cap | stderr warning ("not recorded; delete <path> or raise configuration.history.max_size_mb"); command unaffected |
| History append I/O error | stderr warning; command unaffected |
| Corrupt line on read | skipped with one stderr note; remaining entries shown |
| `--entry` id not found | clear error, exit 1 |
| History disabled / no file on `show cli history` | friendly empty-state, exit 0 |
| id-read race (concurrent CLIs) | accepted; documented |

## Testing (established methodology)

1. **phantasos emitted tests** (fake-SDK fixture, facade-boundary mocking only):
   success + error calls append correct entries (id increments, status/error fields);
   `--dry-run` and meta commands leave no trace; `verbose: true` records bodies;
   cap reached (tiny `max_size_mb` in test config… cap check uses bytes so a 0 value
   forces the warn-skip path) → warning + no write; `show cli history`
   table/`--limit`/`--entry`/empty-state; `.env` file sets `{PREFIX}_HISTORY_ENABLED=false`
   and the config layer honors it (the dotenv fix's regression test); reserved-object
   guard (an IR with object `cli` fails the build with the clear error).
2. **Defaults-sync** auto-covers the new section (existing test).
3. **Gated real-SDK test**: build the real CLI, mocked-facade call writes an entry under
   a tmp HOME, `show cli history` renders it.
4. **Real rebuild** + manual verification on prisma-browser-cli.

## Out of scope (recorded)

- WP2 (Logfile/logging config) and WP3 (Environments) — designed separately, same recipe.
- `request cli history-clear`, automatic trimming/rotation, body redaction.
- Request method/URL capture in entries (conscious v1 trim, see schema).
- `show cli status` / `show cli changelog` / `request cli environment` (separate TODOs;
  the `cli` meta-object created here is their future home).
- Recording meta commands.

## Implementation note (2026-06-12, from quality review)

`history.verbose: true` combined with `--all` records the FULL drained result list as
`response_body` — a single entry can be very large and may overshoot the size cap in
one write (the cap check runs before the append; the NEXT command is then skipped).
Accepted: verbose is opt-in, the cap still bounds growth, one-shot CLI.

## Addendum (2026-06-12): http_method / http_uri captured by default

User-requested reversal of the v1 trim. Every entry that reaches the SDK call now also
carries `http_method` and `http_uri` (full URI incl. query string) BY DEFAULT.

Mechanism — observe, don't re-serialize: every generated SDK method routes through
`api_client.call_api(method, url, …)`, and the serialize step has already appended the
query string to `url` by then. The runtime wraps `api_client.call_api` for the duration
of the real call (restored in `finally`), capturing the first invocation's
`(method, url)` — truthful (the actual outgoing request), zero added serialization
cost. Properties:
- `--all` pagination: the FIRST page's URI is recorded (later pages differ only by cursor).
- Errors raised inside `call_api` propagate AFTER capture → error entries carry the
  fields too. Pre-call failures (body validation) never reach `call_api` → fields
  absent, consistent with their missing `duration_ms`.
- Clients without the openapi-generator shape (test fakes, mocks) degrade silently:
  `getattr` guards → fields absent, never a crash.
