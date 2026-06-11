# Generated CLI: "Common Options" Help Panel — Design

**Date:** 2026-06-11
**Status:** Approved design (grilled with user; all decisions user-confirmed)
**Scope:** phantasos CLI generator — one template; validated on prisma-browser-cli.
**Origin:** UX review of leaf `--help` screens: the five injected cross-cutting options
(`--output`, `--columns`, `--dry-run`, `--verbose`, `--pager`) sit in the default
Options panel mixed with the command's domain flags, drowning the flags a user actually
came to read. Alternatives considered and REJECTED: moving these options to the root
app (root-only is position-rigid in Click — `cli show x --dry-run` would stop working —
and breaks scripts) and dual root+leaf registration (deferred; not needed for the help
problem). Chosen: **Option C — help-only cleanup.**

## Decisions (user-confirmed)

| Topic | Decision |
|---|---|
| Change class | Pure help METADATA: `rich_help_panel` tags only. Zero behavioral change — every flag keeps its leaf position, parsing, defaults, and runtime semantics |
| Panel name | `Common Options` (exactly) |
| Membership | `--output`, `--columns`, `--dry-run`, `--verbose`, `--pager/--no-pager` |
| NOT members | `--all` stays in `Pagination Options` (it composes with limit/cursor/sort). `--help` stays Click's stock option in the default panel (an earlier idea to move it was scrapped — it would require suppressing Click's auto-help and re-implementing it per command) |
| Position | `Common Options` renders LAST ("lowest container") on every leaf help screen |
| In-panel order | `--output`, `--columns`, `--dry-run`, `--verbose`, `--pager` (declaration order) |
| Scope | Generated leaf API commands only (the only commands that carry these options). Root app, verb groups, object sub-groups, and `config init/show` helps are untouched |

## Resulting leaf help layout

```
╭─ Options ──────────────────────────╮   domain path/body flags + --help
╭─ Filter Options ───────────────────╮   (only when the command has filter params)
╭─ Pagination Options ───────────────╮   pagination query params + --all
╭─ Common Options ───────────────────╮   --output --columns --dry-run --verbose --pager
╰────────────────────────────────────╯
```

## Mechanics (verified empirically against installed Typer 0.26)

- Typer renders rich help panels in **first-occurrence declaration order**, with the
  default `Options` panel first. Tagging is sufficient; no ordering API exists or is
  needed.
- **Required reorder:** `--all` (Pagination Options) is currently declared between
  `--columns` and `--dry-run`. On commands with no pagination query params
  (create/update/delete), Pagination Options' first occurrence would then come AFTER
  Common Options' first member, rendering Pagination below Common. Fix: move the
  `all_` declaration ABOVE `output` in the injected block. New declaration order:
  `all_, output, columns, dry_run, verbose, pager`. This is invisible at runtime
  (keyword options; the `_rt.run(...)` call is unchanged).

## Implementation surface

- `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` — the ONLY
  production change: add `rich_help_panel="Common Options"` to the five injected
  options; move `all_` above `output`.
- No changes to: runtime, config, output, app registration, render_cli, cliconfig,
  IR, or any behavior.

## Acceptance criteria / testing (established methodology — behavioral, via the emitted package)

1. **Panel-last structural test** (fake-SDK `emitted` fixture, CliRunner):
   `show widget --help` → parse the `╭─ <title> ─` header lines; assert `Common
   Options` is present and is the LAST panel; assert the five option names appear
   after its header; assert a domain flag (`--id`) appears BEFORE it (in the default
   Options panel).
2. **Non-list command ordering** (the reorder fix): `create widget --help` → both
   `Pagination Options` (carrying `--all`) and `Common Options` present, with
   Pagination Options rendering BEFORE Common Options.
3. Existing help-related tests must stay green unmodified where possible (`--pager`
   presence, filter/pagination panel tests); the full suite + ruff + mypy gate.
4. Real rebuild: `phantasos cli build prisma-browser`, eyeball `show device-group
   --help` and `create device-group --help`.

## Out of scope (recorded)

- `--all` is injected on every command including non-list verbs (create/delete) where
  it is inert — pre-existing; a separate cleanup candidate.
- Root-level/dual registration of cross-cutting flags (`cli --dry-run show x`) —
  consciously deferred; revisit only if leaf-position-only proves insufficient.
- `config init/show` help layout; COMMANDS.md/docs rendering of panels.

## Addendum (2026-06-11): panel de-suffixing

User-confirmed follow-up after UX review: the "Options" suffix is redundant on the
tagged panels (every panel contains options). Renames: `Filter Options → Filters`,
`Pagination Options → Pagination`, `Common Options → Common`. The DEFAULT `Options`
panel is deliberately KEPT: renaming it (proposal: "Command") was reviewed and
rejected — "Commands" conventionally means subcommands (the root help has exactly
that panel), and the default title is Typer's, so changing it requires either a
global `typer.rich_utils.OPTIONS_PANEL_TITLE` override (leaks into root/config
screens, version-coupled) or tagging every domain flag (orphans Click's auto
`--help` in a one-line residual panel). Resulting leaf layout:
`Options / Filters / Pagination / Common`.
