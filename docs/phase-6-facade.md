# Phase 6 — Native resource facade  ✅

## Goal
The pan-scm-sdk-style entry point: `client.<resource>.<operation>()` with cursor pagination.

## What was built
`oag-overlay/facade.py::Client`:
- Constructor binds all **13 resources** as attributes, each the generated `*Api` instance:
  `users, user_groups, user_requests, devices, device_groups, applications,
  application_groups, plugins, security_policy, sign_in_policy, access_and_data_policy,
  customization_policy, configuration_management`.
- `Client.from_env()` / `Client.from_credentials(...)` — build an authenticated client
  (Phase 4 auth + Phase 5 retries) in one call.
- `client.paginate(client.users.list_users, **filters)` — cursor-following iteration.
- Context manager (`with Client.from_env() as client: …`) releasing the underlying pool.

Usage:
```python
from prisma_browser.extras import Client
with Client.from_env() as client:
    for user in client.paginate(client.users.list_users, limit=100):
        ...
    rule = client.security_policy.get_security_rule_by_id(rid)
```

## Codegen fix required (also serves Phase 8)
The facade's policy reads hit an OAG **oneOf bug**: `PolicyItem` (`oneOf: RuleSummary |
Section`) and 8 other oneOf models raise `ValueError("Multiple matches …")` when more than
one branch validates the same payload (branches share structure / extra fields tolerated).
Added an idempotent patch in `apply_patches.py` (`patch_oneof_first_match`, 9 models):
`from_json` now **returns on the first matching branch** instead of counting and raising —
the same behavior the prototype (openapi-python-client) used. The field validator is
`isinstance`-based, so the concrete instance remains unambiguous.

## Acceptance evidence (live)
- 13/13 resources wired; `with Client.from_env()` opens/closes cleanly.
- `client.paginate(client.users.list_users)` iterates.
- All four policy reads deserialize: security 1, sign-in 1, access-and-data 4,
  customization 1 — items typed `RuleSummary` (these policies contain only rules).
- 426 modules import, 95 operations.

## Known limitation
oneOf first-match can mis-type when two branches genuinely match the same object
(no discriminator). The current tenant's policies are all rules, so unaffected. A
discriminator-based deserialization would be more precise — noted as future polish.

## Files
`oag-overlay/facade.py`, `oag-overlay/__init__.py`, `apply_patches.py` (oneOf patch).
