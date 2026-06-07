# TODO

## Write tests for the ADEM SDK

The ADEM SDK is generated to the sibling `../adem-sdk/` but has **no test suite yet**
(unlike `../prisma-browser-sdk/`, which has `tests/`). Add an offline pytest suite in
`adem-sdk/tests/`, mirroring the prisma-browser-sdk layout but scoped to ADEM's component
set (`auth` + `facade` only — `pagination=None`, `errors=None`).

Build first: `sdkgen build transformations/adem.py` (writes the SDK to `../adem-sdk/`).

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

## Follow-up: consider a Typer CLI

The CLI is currently argparse (`sdkgen.cli:main`). The project template ships a Typer
scaffold; porting the one `build` command to Typer would add `--help` polish and shell
completion (and align with the template's CLI docs). Tracked as optional; argparse works.
