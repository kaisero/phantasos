# Phase 8 — Live validation parity  ✅

## Goal
Confirm the OAG SDK reaches ≥ parity with the prototype against the live (entitled) tenant,
with **0 deserialization errors**.

## Result (tenant TSG 1170082768)
`oag-examples/sweep_get_endpoints.py`:

| Metric | OAG SDK | Prototype (same tenant) |
|---|---|---|
| GET endpoints | 31 | 31 |
| 200 OK | **21** | 21 |
| Deserialization errors | **0** | 0 |
| Skipped (env: empty collections / no policy sections) | 10 | 10 |

The 10 skips are environmental — the tenant has no devices, user-groups, device-groups,
plugins, application-groups, or user-requests to fetch by id, and its policies contain only
rules (no sections). Not SDK issues.

## Enum gaps (accumulated, `findings/enum_gaps.md`)
| Enum | Undeclared value(s) |
|------|---------------------|
| `AuthenticationFactorPinCodeControlMethod` | `passkey` |
| `CustomApplicationAllOfType` / `CustomApplicationType` | `catalog` |
| `FirewallVendorName` | `OpenBSD` |
| `UserProvider` | `cie`, `scm` |

(`CustomApplicationAllOfType` vs `CustomApplicationType` is the same gap under the two
generators' different model names. `OpenBSD`/`cie` came from the earlier tenant's sweep —
findings accumulate across runs.)

## Model-fidelity check (the Phase 2 warning)
The generator's `Required var urls/primaryUrl/mode not in properties` warnings did **not**
cause runtime failures in this read sweep — all 21 reachable endpoints deserialized cleanly,
including the application-polymorphism (`ApplicationItem` oneOf) and security-policy
(`SecurityControls`) schemas. The oneOf first-match patch (Phase 6) was required for the
polymorphic reads. A deeper write-path/field-completeness audit remains future work
(out of scope — write path is not validated in this migration).

## Verdict
**Parity met** for the read surface: same coverage, zero deserialization errors, same enum
gaps discovered.
