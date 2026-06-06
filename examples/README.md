# Examples

Read-only example scripts that run against a live Prisma Browser tenant.

## Setup
Populate `../.env` (see `../.env.example`) with `CLIENT_ID`, `CLIENT_SECRET`, and
`SCOPE` (`tsg_id:<your-TSG-ID>`). Then run any example via the helper, which wires
up dependencies and the package path:

```
./examples/run.sh                                  # validate_live.py (default)
./examples/run.sh examples/list_users.py
./examples/run.sh examples/sweep_get_endpoints.py
```

## Scripts
| Script | What it does |
|--------|--------------|
| `validate_live.py` | End-to-end smoke test: auth → list → paginate → typed 404 error |
| `list_users.py` | Paginate all users; summarize by status and provider |
| `list_applications.py` | Paginate applications; group by type |
| `list_devices.py` | Paginate devices; summarize by status and OS |
| `sweep_get_endpoints.py` | Call **every** GET endpoint; report enum gaps + errors to `../findings/` |
| `probe_policy_403.py` | Capture the real request/response for the policy GETs that 403; write `../findings/policy_403.md` |

## Discovering spec drift
`sweep_get_endpoints.py` exercises all 31 GET endpoints (resolving `{id}`/`{type}`
params from list responses) and records any enum value the live API returns that
the OpenAPI spec doesn't define — written to `../findings/enum_gaps.{json,md}` for
reporting upstream. Unknown enum values don't crash deserialization (the SDK uses a
lenient enum base); they're collected and surfaced instead.

All scripts are strictly read-only — they issue only GET requests.
