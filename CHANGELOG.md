# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-08-17

### Added

- **Idempotent sync in generated SDKs.** You can now describe the state a resource
  should be in and let the SDK create it, update it, or leave it alone, instead of
  writing that create-or-update logic yourself.
- **CLIs that span a multi-spec API.** A generated CLI can now cover an API split
  across many specs under one command tree, shipped here as a prisma-access CLI
  reaching all twelve of its service groups.
- **Documentation sites for what you generate.** A generated SDK and a generated CLI
  can each emit a browsable documentation site with a quickstart, a full reference,
  and runnable examples.
- **Authentication you control.** Generated CLIs store several named credential sets
  and stay signed in between commands, and a generated SDK client can be built from
  an access token you already hold.
- **New posture product.** phantasos now ships the configuration to generate a
  working SDK and CLI for Palo Alto Networks Posture Management, covering posture
  checks and BPA uploads.

### Changed

- **Breaking:** SDK calls now go through typed resource wrappers rather than the raw
  generated API classes — `client.<object>.<verb>(...)` — and walking a full
  collection is one `list(all_pages=True)` call instead of a loop you write.
- **Breaking:** Connection settings such as region come from the active environment
  or an environment variable; the per-command `--region` and `--tenant` flags are
  gone, and the redundant tenant header is no longer sent.
- **Generated CLIs start much faster.** A CLI now loads only the command you actually
  invoked, cutting cold start roughly three-and-a-half fold — two seconds to half a
  second on a 648-command CLI.
- **prisma-browser follows its refreshed API.** Its SDK and CLI now expose the
  partial-move reordering endpoint for all four policy types, alongside the existing
  full-replace reorder.

### Fixed

- **A generated project passes its own quality gate.** Building an SDK with
  idempotent sync no longer exits with type-check and formatting failures that the
  generated project could never satisfy.
- **Generated CLIs print the payload, not the plumbing.** Responses from endpoints
  with union types no longer leak generator scaffolding into JSON and YAML output.
- **Clear errors instead of tracebacks.** Starting a generated CLI with no
  credentials, or listing an object the API only exposes by id, now tells you what to
  do rather than crashing.
- **Specs that used to produce broken models now generate cleanly.** Unicode-property
  patterns and certain union wrappers no longer yield an SDK that fails on import or
  when parsing a response.

## [0.1.0a1] - 2026-06-13

### Added

- **Generated command-line interfaces.** phantasos can now turn a built SDK into a
  working CLI, with verb-first commands, table output, layered user configuration,
  and a command history.

### Changed

- **Breaking:** `phantasos build` is now `phantasos sdk build`, joined by
  `phantasos cli discover` and `phantasos cli build`.

### Fixed

- **An installed phantasos actually runs.** A pip-installed copy no longer crashes on
  import or fails to build a CLI because required files were missing from the wheel.

## [0.0.1] - 2026-01-01

### Added

- **First release.** phantasos generates a self-contained Python SDK from an OpenAPI
  spec.

[Unreleased]: https://github.com/kaisero/phantasos/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/kaisero/phantasos/compare/v0.1.0a1...v0.1.1
[0.1.0a1]: https://github.com/kaisero/phantasos/compare/v0.0.1...v0.1.0a1
[0.0.1]: https://github.com/kaisero/phantasos/releases/tag/v0.0.1
