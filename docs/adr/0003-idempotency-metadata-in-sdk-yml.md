# Idempotency metadata lives in sdk.yml, not ansible.yml

**Status:** proposed

Because the idempotent sync operation is an SDK capability (see ADR-0002), the
per-resource metadata it needs — natural `identity`, `read_only`/`computed` field
classifications, and which fields are the SCM `scope` (container) — lives in
`products/<name>/sdk.yml` and is baked into the generated SDK. `ansible.yml`
keeps only genuinely Ansible-specific configuration (galaxy namespace/name, module
include/exclude, connection/httpapi settings). The SDK never reads `ansible.yml`.

We decided this instead of keeping the annotations in `ansible.yml` (as the
original feasibility report sketched) and passing them into the SDK at call time,
because that would make the SDK capability correct only when each caller supplies
the right field lists — re-introducing the per-consumer configuration drift that
ADR-0002 exists to eliminate, and forcing the CLI to carry its own copy. One
authoritative definition in `sdk.yml` means CLI and Ansible consume identical
idempotency behavior.

**Consequence:** `sdk.yml` grows a per-resource idempotency block; the existing
`operations:` override style is the natural home for it.
