# sdkgen

Generate native, self-contained Python SDKs from OpenAPI specs. `sdkgen` wraps
[OpenAPI Generator](https://openapi-generator.tech/) (`python`/Pydantic v2) and adds
generic spec preprocessing, codegen-bug patches, and **vendored, templated components**
(auth, pagination, errors, a resource facade) selected per spec. Each spec is described
by a small Python config (`sdk.py`); the generated SDK is written to its own directory
and depends only on `httpx`/`urllib3`/`pydantic`.

## Quickstart
```bash
pip install -e ".[generated]"          # framework + deps the generated SDK imports
sdkgen build specs/prisma-browser/sdk.py
```
Needs a JRE (11+) on `PATH`; the OpenAPI Generator jar is fetched once to
`~/.cache/sdkgen` (override with `SDKGEN_CACHE`).

The build runs: **preprocess** (generic transforms + the spec's `preprocess` hook) →
**generate** (OpenAPI Generator) → **patch** (apostrophe enums / lenient enums / oneOf
first-match) → **vendor** (render selected component templates into `<package>/extras/`,
write `_about.py` provenance) → **smoke** (import every module + count operations).

## Describing a spec (`sdk.py`)
```python
from sdkgen import SdkConfig, OAuthClientCredentials, CursorPagination, NestedError, Facade

CONFIG = SdkConfig(
    spec="./spec.yaml", package="my_sdk", base_url="https://api.example.com",
    project_dir="../my-sdk",                       # generated SDK lands here
    auth=OAuthClientCredentials(token_url="https://auth.example.com/oauth2/token"),
    pagination=CursorPagination(), errors=NestedError(), facade=Facade(),
)

def preprocess(spec):                              # optional spec-specific quirks
    from sdkgen.preprocess import hoist_items, tag_operations
    ...
```
Full guide + component param reference: [`docs/AUTHORING_A_SPEC.md`](docs/AUTHORING_A_SPEC.md).

## Layout
| Path | What |
|------|------|
| `sdkgen/` | the framework package (`config`, `preprocess`, `generate`, `patches`, `render`, `smoke`, `cli`) |
| `sdkgen/components/*.jinja` | vendored component templates (auth / pagination / errors / facade) |
| `specs/prisma-browser/sdk.py` | example spec config (Prisma Browser); builds to a **sibling** `../prisma-browser-sdk/` |
| `specs/prisma-browser/prisma-browser.yaml` | the example spec's OpenAPI source |
| `tests/` | framework engine tests (`test_framework.py`) |
| `docs/` | architecture, re-arch plan, authoring guide, and the prototype migration history |
| `pyproject.toml` | packaging (`console_scripts: sdkgen = sdkgen.cli:main`) |

Generated SDKs are **not** kept in this repo — each builds into its own directory
(e.g. the Prisma Browser SDK builds to the sibling `../prisma-browser-sdk/`, which owns
its own tests, examples, and `.env.example`).

## Tests
```bash
python -m pytest tests/ -q                # framework engine tests
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/REARCH_PLAN.md`](docs/REARCH_PLAN.md) for the design and the parity sign-off.
