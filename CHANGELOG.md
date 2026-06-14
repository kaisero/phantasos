# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Agent-facing context docs (`.agents/context/`) — a modular, on-demand technical
  doc set for in-repo coding agents: an `index.md` system map, per-subsystem
  deep-dives (sdk-generator, cli-generator, components, product-config, scaffold,
  phantasos-cli, harness-and-testing, release-workflow), and cross-cutting
  `decisions.md` / `goals-non-goals.md`. An AST generator (`nox -s context`,
  `tools/context_docs.py`) fills the mechanical sections (module maps, public API)
  with a `--check` mode enforced by a test; discoverable via a root `AGENTS.md`
  and a `CLAUDE.md` pointer. Includes an A/B evaluation harness (`tools/ab_eval/`).
- Generated CLIs now write a structured, rotating JSON-Lines log to `~/.{distribution}/logs/{distribution}.jsonl` (private `0o600`, gzip-rotated). Python `warnings` (notably the SDK's lenient-enum pass-through) and CLI diagnostics are captured into this file instead of the terminal; a single terse stderr line at exit summarizes any unknown API enum values. A new `logging` config section (`level` — trace/debug/info/warning/error/critical — and `file`) joins the layered-config flow, with `{PREFIX}_LOGGING_LEVEL` / `{PREFIX}_LOGGING_FILE` env overrides.
- `config set <key> <value>` and `config unset <key>` for generated CLIs: write/remove options in `config.yml` (aliases `loglevel`/`logfile`; values coerced by type; unknown keys and invalid values exit `2`). NOTE: writing `config.yml` strips the comments that `config init` wrote — run `config init --force` to restore the commented template.
- Generated CLIs with an auth component now support named environments: stored in `~/.{distribution}/environments.yml` (top-level `environments:` and `default_environment:` keys, with `${VAR}` references resolved at read time), an `--environment/-e` flag, and a `{PREFIX}_ENVIRONMENT` selector. Per-field credential env vars override the active environment.
- Top-level `environment` command group (auth CLIs only; shown in the `--help` "CLI" panel beside `config`): `create` (per-credential-field options built dynamically from the auth component; secrets prompted with input hidden and stored verbatim, including `${VAR}` references), `activate`, `show` (names only — never values/secrets; marks the active environment), and `delete` (`--force` required to remove the active environment). The first environment created is auto-activated.

### Fixed

- Generated CLIs (with an auth component) now report a clean, actionable error instead of a raw traceback when no credentials are configured on the first command: a descriptor-driven pre-flight names the missing required credential variables (and the active environment, if any) and points to both `environment create` and the credential env vars (exit code `2`). A genuine auth failure when credentials *are* present (e.g. a token-endpoint error) is likewise reported cleanly with exit code `1`; `--verbose` still surfaces the traceback. The SCM `base_url` credential is now correctly treated as optional (the SDK host has a default).

### Removed

- Obsolete `docs/ARCHITECTURE.md` (a stale "proposal" describing a superseded
  layout) and its references — superseded by the `.agents/context/` set; the
  published-site nav entry is dropped (a fresh architecture page belongs to the
  user-facing docs rework).

## [0.1.0a1] - 2026-06-13

### Added

- Generated CLI subsystem (Typer + Rich) from built SDKs — verb-first set/del/show, IR-driven
- cli.yml-driven config: per-op query defaults, curated table columns (`--columns`)
- Layered user config + auto-pager + JSONL command history for generated CLIs
- Diagnostics/error UX overhaul (stderr facade, `--quiet`, help panels)
- SDK generator: oneOf discriminator lookup
- SDK generator: retry-with-jitter (Tier-1 component) + typed `RateLimitException` (Tier-2 `exceptions.mustache`)

### Changed

- **Breaking:** host CLI moved to Typer — `phantasos build` is now `phantasos sdk build`; adds `phantasos cli discover` / `phantasos cli build`
- Generator code split into `generator/{sdk,cli}` packages

### Fixed

- `typer` is now a runtime dependency (was dev-only — a pip-installed CLI crashed on import)
- The wheel now ships the generated-CLI templates + `cli_overrides` (were absent — `phantasos cli build` failed from a wheel)

## [0.0.1] - 2026-01-01

### Added

- Initial release of phantasos.

[Unreleased]: https://github.com/kaisero/phantasos/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/kaisero/phantasos/compare/v0.0.1...v0.1.0a1
[0.0.1]: https://github.com/kaisero/phantasos/releases/tag/v0.0.1
