# OAG SDK examples

Read-only examples for the OpenAPI-Generator SDK (`oag-sdk/`), using the `Client` facade.

## Setup
Populate `../.env` (`CLIENT_ID`, `CLIENT_SECRET`, `SCOPE=tsg_id:<id>`). Then:

```
./oag-examples/run.sh                                   # validate_live.py
./oag-examples/run.sh oag-examples/sweep_get_endpoints.py
./oag-examples/run.sh oag-examples/list_users.py
```

| Script | What it does |
|--------|--------------|
| `validate_live.py` | auth → list → paginate → read policy → typed 404 |
| `sweep_get_endpoints.py` | every GET endpoint (auto-discovered) → enum gaps in `../findings/` |
| `list_users.py` / `list_applications.py` / `list_devices.py` | paginated summaries via the facade |

All scripts are strictly read-only (GET only).
