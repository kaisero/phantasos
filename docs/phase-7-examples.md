# Phase 7 — Examples + findings re-port  ✅

## Goal
Re-port the prototype's examples to the OAG facade and reproduce the findings tooling.

## What was built (`oag-examples/`)
- `_common.py` — loads `../.env`, returns a facade `Client` (`Client.from_env()`).
- `validate_live.py` — auth → list → paginate → read security policy → typed 404.
- `sweep_get_endpoints.py` — **auto-discovers** GET ops by introspecting each generated
  method's `_serialize` (`method='GET'`), resolves `{id}`/`{type}` params from list
  responses (unwrapping oneOf items), calls all of them, and accumulates enum gaps into
  `findings/enum_gaps.{json,md}`.
- `list_users.py` / `list_applications.py` / `list_devices.py` — paginated summaries.
- `run.sh` — runs an example with deps + package path wired up.

## Acceptance evidence (live)
- `validate_live.py`: all four steps pass (auth, pagination, policy read, `NotFoundException`).
- Workflows run: users (1, provider `scm`), applications (100, type `catalog`), devices (0).

## Difference from prototype
Calls go through the resource facade (`client.users.list_users`, `client.paginate(...)`)
instead of `module.sync_detailed(client=...)`. The sweep discovers GET ops by introspection
rather than reading `_get_kwargs`, since OAG structures methods differently.
