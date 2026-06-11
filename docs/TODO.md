# TODO

## README.md

README is currently too verbose and not very user / developer friendly. Change README to include a brief project description, quickstart guide and link to mkdocs

## CLI Paging Issue

It looks like --all / --paging capabilities are not working in generated cli - always maxed at 100 entries

## Pager Output

CLI should have a --pager option to utilise rich pager for large outputs

## README.md for Prisma Browser CLI

Change README to include a brief project description, quickstart guide and link to mkdoc

## Mkdocs for Generated CLIs

Mkdocs currently does not render meaningful docs. I want a documentation page with a quickstart guide, command reference, capability overview and supported operations per resource

## Yaml Pretty Print

The --output yaml option currently dumps yaml output non-colored to stdout. This needs to be adapted to rich output to be more user-friendly

## User-Facing CLI Configuration File

Auto-Generated CLI should be able to load a user-specific configuration file that can hold multiple environments identified by name. Each environment should be able to override
to .env specific configuration for authentication and advanced options like logging level, logfile location, historyfile (enable/disable), historyfile location

## Auto-Setup Command

CLI should have an interactive command to setup the configuration file and ask through options, showcasing the defaults so user can override if necessary

## History File and Show command

CLI should provide a history file so command execution is documented in a organized manner. The history file should be in json format to tag metadata to commands (date, commadn, request, response, status(success, errors, warnings)
CLI should have a `show cli history` command to view the command history (only the commands)
CLI should have a `show cli history --verbose` to view it as a table with the various fields (date, command, status)

## Status Command

CLI should have a `show cli status` command that shows auth status and loglevel of the cli and also the active environment name

## Request CLI Environment Change

CLI should have a `request cli environment <name>` command that checks the config file and switches to another environment 

## Request CLI Changelog

CLI should have a `show cli changelog` command that pretty prints the CHANGELOG.md provided in the project so users can check what features were added in recent versions


## Write tests for the ADEM SDK

The ADEM SDK is generated to the sibling `../adem-sdk/` but has **no test suite yet**
(unlike `../prisma-browser-sdk/`, which has `tests/`). Add an offline pytest suite in
`adem-sdk/tests/`, mirroring the prisma-browser-sdk layout but scoped to ADEM's component
set (`auth` + `facade` only — `pagination=None`, `errors=None`).

Build first: `phantasos build transformations/adem.py` (writes the SDK to `../adem-sdk/`).

- [ ] `tests/conftest.py` — put the SDK on `sys.path` (copy from `prisma-browser-sdk/tests/conftest.py`)
- [ ] `test_auth.py` — `AdemConfiguration` / `TokenManager` / `api_client_from_env`: bearer-JWT
      token fetch + refresh, env vars (`CLIENT_ID`/`CLIENT_SECRET`/`SCOPE`, `ADEM_BASE_URL` override)
- [ ] `test_facade.py` — `Client` binds the 8 controllers (agent / application / internet / nav /
      route / rum / zoom_participant / zoom_qos); `from_env` present; **no** `paginate` method
- [ ] `test_lenient_enums.py` — unknown enum values pass through as pseudo-members (18 inline enums)
- [ ] `test_models.py` — a model tolerates an unknown enum; a `oneOf` response (Summary vs Series)
      deserializes via the first-match patch
- [ ] (optional) live read-only validation against an entitled tenant, like
      `prisma-browser-sdk/examples/validate_live.py`

Notes:
- ADEM has `pagination=None` and `errors=None`, so **no** `test_pagination.py` / `test_errors.py`.
- The framework CI already smoke-builds ADEM; once the SDK suite exists, run it where the SDK
  lives (the sibling), not in the generator repo (generated-code tests belong to the generated SDK).

## Harmonize ID path-parameter naming across generated SDKs

Surfaced while designing the CLI generator (`prisma-browser-cli`). The generated SDK uses
**inconsistent names for the resource-id path parameter** across operations — e.g.
`id` (applications, rules, sections), `device_group_id` (device groups),
`device_status_change_request` (a body, not a path id), etc. This forces any downstream
consumer (the CLI's create-vs-patch-vs-update classifier, in particular) to guess which
parameter is "the id".

Decision: **harmonize this in the SDK layer (phantasos), not in the CLI.** The CLI should be
able to assume a single canonical id parameter. Likely a generic preprocess/patch transform
(or a `sdk.yml` rename rule) that normalizes path-id parameters to a consistent name/shape.

- [ ] Audit id path-param names across all operations in each product spec
- [ ] Design a normalization transform (rename to a canonical `id`, or expose a stable accessor)
- [ ] Apply + re-smoke; confirm the CLI generator can rely on the canonical id
- [ ] Document the convention in `docs/AUTHORING_A_SPEC.md`

## Follow-up: consider a Typer CLI

The CLI is currently argparse (`phantasos.cli:main`). The project template ships a Typer
scaffold; porting the one `build` command to Typer would add `--help` polish and shell
completion (and align with the template's CLI docs). Tracked as optional; argparse works.

## Undiscriminated oneOf × lenient enums — wrong-variant deserialization

`useOneOfDiscriminatorLookup=true` (2026-06-11) fixes oneOf variant dispatch only for
schemas that declare a `discriminator`. Undiscriminated oneOfs (all 11 in adem, ~3 in
prisma-browser) still use trial deserialization patched to first-match
(`patches.patch_oneof_first_match`), and `LenientStrEnum` makes a wrong first match
succeed silently — the exact mechanism behind the ApplicationItem bug. Candidate
fixes: add discriminators via spec preprocess transforms where a suitable property
exists, or make enum leniency strict during oneOf trial deserialization (fragile —
analyzed 2026-06-11, see plans/2026-06-11-oneof-discriminator-lookup.md).

Drift behavior with the lookup (verified + accepted 2026-06-11): unknown discriminator
values fall back to the trial-deserialization loop (today's lenient behavior — a new
server-side type keeps list calls working); a missing or empty `type` field raises a
clear `ValueError` (missing was already fatal pre-flag; empty was silently mis-typed).
