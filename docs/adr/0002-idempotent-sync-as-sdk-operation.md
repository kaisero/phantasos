# Idempotent sync is an SDK operation, not per-consumer orchestration

**Status:** proposed

To support generating an Ansible collection (and richer CLI `apply`) from
phantasos, the generated SDK's resource facade gains a high-level idempotent
**sync operation** — `apply(desired, *, scope, check_mode) -> Result` and
`absent(identity, *, scope, check_mode) -> Result` — that internally performs
fetch → diff → create/update/delete/no-op. The lower-level primitives (`fetch`,
`diff`) are also public.

We decided this instead of exposing only primitives and letting each consumer
orchestrate, because the reference community project for the same API family
(cdot65/pan-scm-ansible) does exactly that and pays for it: every Ansible module
re-implements a hand-maintained whitelist `needs_update`, which silently ignores
any field not on the list, so drift on unlisted fields is missed and the logic
diverges per resource. Defining the fetch→diff→mutate flow **once in the SDK**
means the CLI and the Ansible module_utils share one tested implementation, and
idempotency correctness lives next to the models it reasons about.

**Considered options:** (a) primitives only, orchestration per consumer —
rejected (duplication + whitelist-drift bug class); (b) high-level sync operation
plus public primitives — chosen.

**Consequences:** the SDK owns `check_mode`/dry-run (mapped onto the existing
`_serialize` request-rendering path), the shape of a `Result`
(changed/before/after/diff), and not-found semantics — these become the
consumer-facing contract the later Ansible plan builds against.
