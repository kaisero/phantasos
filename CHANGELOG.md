# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
