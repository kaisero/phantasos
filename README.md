# phantasos

[![CI](https://github.com/kaisero/phantasos/actions/workflows/ci.yml/badge.svg)](https://github.com/kaisero/phantasos/actions/workflows/ci.yml)
[![Docs](https://github.com/kaisero/phantasos/actions/workflows/docs.yml/badge.svg)](https://kaisero.github.io/phantasos/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Generate native, self-contained Python SDKs from OpenAPI specs. `phantasos` wraps
[OpenAPI Generator](https://openapi-generator.tech/) (`python`/Pydantic v2) and adds
generic spec preprocessing, codegen-bug patches, and **vendored, templated components**
(auth, pagination, errors, a resource facade) selected per spec. Each product is described
by a declarative `products/<product>/` directory containing `openapi.yml`, `sdk.yml`, and
optionally `templates/` (custom component Jinja files) and `hooks.py` (Python preprocessing
hooks); the generated SDK is written to its own directory and depends only on
`httpx`/`urllib3`/`pydantic`.

## Quickstart
```bash
pip install -e .                       # phantasos itself — no SDK runtime deps needed
phantasos build prisma-browser
```
No system Java required — see [Requirements](#requirements). The OpenAPI Generator jar and
a JRE are fetched once to `~/.cache/phantasos` (override with `PHANTASOS_CACHE`). The smoke
step import-checks the built SDK in an isolated venv built from the SDK's own
`requirements.txt`, so phantasos needs none of the SDK's runtime deps; pass `--no-smoke` to
skip it (offline builds).

The build runs: **preprocess** (generic transforms + the spec's `preprocess` hook) →
**generate** (OpenAPI Generator) → **patch** (apostrophe enums / lenient enums / oneOf
first-match) → **vendor** (render selected component templates into `<package>/extras/`,
write `_about.py` provenance) → **smoke** (import every module + count operations).

## Requirements

`phantasos build` runs OpenAPI Generator, which needs a Java runtime. **You do not
need to install Java** — on first build, phantasos downloads a pinned, checksum-verified
[Eclipse Temurin](https://adoptium.net/) JRE 17 for your platform into `~/.cache/phantasos`
(a one-time ~40 MB download; override the location with `PHANTASOS_CACHE`).

Supported platforms for auto-provisioning: Linux (x64/arm64), macOS (x64/arm64),
Windows (x64). On any other platform — or to use your own JVM — install a JRE 11+ and set
`PHANTASOS_JAVA=/path/to/java`.

## Describing a product (`products/<product>/sdk.yml`)
```yaml
# products/<product>/sdk.yml
package: my_sdk
output: ../../../my-sdk
base_url: https://api.example.com
auth: {type: oauth_client_credentials, token_url: https://auth.example.com/oauth2/token}
pagination: {type: cursor}
errors: {type: nested}
facade: true
```
Full schema reference + hooks guide: [`docs/AUTHORING_A_SPEC.md`](docs/AUTHORING_A_SPEC.md).

## Layout
| Path | What |
|------|------|
| `src/phantasos/` | the framework package (`config`, `productconfig`, `preprocess`, `generate`, `patches`, `render`, `smoke`, `cli`) |
| `src/phantasos/components/*.jinja` | vendored component templates (auth / pagination / errors / facade) |
| `products/<product>/openapi.yml` | a product's OpenAPI source spec |
| `products/<product>/sdk.yml` | a product's declarative build config (package, output, components, transforms) |
| `products/<product>/templates/` | optional per-product custom component Jinja templates |
| `products/<product>/hooks.py` | optional Python hooks (`preprocess(spec)` / `patch(pkg_dir)`) |
| `tests/` | framework unit tests |
| `docs/` | architecture docs and authoring guide |
| `pyproject.toml` | packaging (`console_scripts: phantasos = phantasos.cli:main`) |

Generated SDKs are **not** kept in this repo — each builds into its own directory
(e.g. the Prisma Browser SDK builds to the sibling `../prisma-browser-sdk/`, which owns
its own tests, examples, and `.env.example`).

## Development

[uv](https://docs.astral.sh/uv/) + [nox](https://nox.thea.codes/) drive every check (one
source of truth for local and CI):

```bash
uv sync --all-groups       # venv + locked deps (writes/uses uv.lock)
uv run nox                  # lint (ruff) + type-check (mypy strict) + tests (pytest+cov) + docs
uv run nox -s smoke         # build the example SDKs end-to-end (needs JDK 17)
uv run pre-commit install   # enable git hooks
```

Run a single check, e.g. `uv run nox -s tests` or `uv run nox -s lint`. The engine tests
alone: `python -m pytest tests/ -q`.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/REARCH_PLAN.md`](docs/REARCH_PLAN.md) for the design and the parity sign-off.
