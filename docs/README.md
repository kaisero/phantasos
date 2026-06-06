# Migration docs — OpenAPI Generator (python/Pydantic) SDK

Per-phase outcomes of migrating the Prisma Browser SDK from `openapi-python-client`
to OpenAPI Generator's `python` generator (resource classes + Pydantic v2).
Plan: [`../MIGRATION_PLAN.md`](../MIGRATION_PLAN.md).

| Phase | Doc | Outcome |
|-------|-----|---------|
| 1–2 | [phase-1-2-build.md](phase-1-2-build.md) | Local `make` pipeline; 95 ops; clean import; deterministic |
| 3 | [phase-3-lenient-enums.md](phase-3-lenient-enums.md) | Lenient enums (str+int), unknown values preserved |
| 4 | [phase-4-auth.md](phase-4-auth.md) | OAuth2 client-credentials, auto-refresh |
| 5 | [phase-5-transport-pagination-errors.md](phase-5-transport-pagination-errors.md) | Retries, pagination, typed errors |
| 6 | [phase-6-facade.md](phase-6-facade.md) | `client.<resource>.<op>()` facade + oneOf fix |
| 7 | [phase-7-examples.md](phase-7-examples.md) | Examples re-port + sweep |
| 8 | [phase-8-live-validation.md](phase-8-live-validation.md) | Live parity: 21/31, 0 errors |
| 9 | [phase-9-tests.md](phase-9-tests.md) | 16 offline pytest |
| 10 | [phase-10-cutover.md](phase-10-cutover.md) | Parity sign-off + cutover checklist |

## Quickstart
```
make build && make test
./examples/run.sh examples/validate_live.py   # needs ../.env
```

> Note: phase docs 4–9 were written before cutover and reference the pre-cutover
> directory names (`oag-sdk/`, `oag-overlay/`, `oag-examples/`). Post-cutover these are
> `prisma-browser-sdk/`, `overlay/`, and `examples/` respectively.
