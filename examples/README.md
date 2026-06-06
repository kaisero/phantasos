# Examples

Read-only examples for the SDK (`prisma-browser-sdk/`), using the `Client` facade.

## Setup
Populate `../.env` (`CLIENT_ID`, `CLIENT_SECRET`, `SCOPE=tsg_id:<id>`). Then:

```
./examples/run.sh                                   # validate_live.py
./examples/run.sh examples/sweep_get_endpoints.py
./examples/run.sh examples/list_users.py
```

| Script | What it does |
|--------|--------------|
| `validate_live.py` | auth → list → paginate → read policy → typed 404 |
| `sweep_get_endpoints.py` | every GET endpoint (auto-discovered) → enum gaps in `../findings/` |
| `list_users.py` / `list_applications.py` / `list_devices.py` | paginated summaries via the facade |

All scripts are strictly read-only (GET only).
