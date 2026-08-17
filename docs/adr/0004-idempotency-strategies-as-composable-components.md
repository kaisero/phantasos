# Idempotency strategies are composable per-resource components

**Status:** proposed

The idempotent-sync engine is decomposed into a thin orchestrator plus small,
swappable **strategy components**, mirroring how `pagination` is already a
per-product component (`type: cursor | offset`). The axes that genuinely vary
across products/resources each become a component family with named variants,
selected per resource and vendored as individual modules:

- **fetch** — `list_scan` | `list_filter` | `get` (singleton): find the existing
  object by identity (+scope), return `Model | None`.
- **mutate** — `put_rmw` | `patch_minimal`: turn a `Diff` into a wire mutation.
- **materialize** — `direct` | `get_after_write`: produce the post-state `after`
  from a mutation response (handles id-only envelopes — F3).

The orchestrator (`SyncEngine`/`SyncMixin`, interface `apply`/`absent`/`fetch`/
`diff`) owns the uniform control flow (identity extraction, the desired-subset
diff, `check_mode`, create-body construction) and delegates the varying steps to
the strategy named in each resource's baked `_idempotency` metadata. The generator
vendors the *union* of strategy modules its opted-in resources reference (finer
grained than `pagination`, which is one-per-product, because fetch/mutate differ
between resources of the same product).

We chose this over a single monolithic `SyncMixin` with inline `if meta[...]`
branches because — validated live against two very different products
(prisma-access: single model, scope, PUT-replace, full-payload create;
prisma-browser: multi-model, no scope, PATCH, id-only create) — **fetch, mutate,
and materialize each already have 2+ real variants**, so by the "two adapters make
a real seam" rule they are real seams, not hypothetical. Naming them makes the
engine open/closed: a third spec that varies along a known axis is config only; a
genuinely new variant is a new strategy module (a file + a `sdk.yml` value), not a
monolith edit; and a novel product can supply a custom strategy via the existing
`type: ./path.jinja` component escape hatch or `hooks.py` — without editing the
shared engine or forking it (the pan-scm per-module-duplication failure this whole
effort avoids).

**Consequences:** more moving parts than a monolith (an engine core + N small
strategy modules + a per-resource selection/registry in the `_idempotency`
metadata) and higher upfront effort; each strategy is independently unit-testable;
the interface callers learn is still four methods; the diff's per-field
normalization stays in the engine core with a projection hook (promote to a
`compare` family only when a second projection type exists — YAGNI). Supersedes the
monolithic-`SyncMixin` shape sketched in spec §5 and the original implementation
plan; both are revised to this decomposition.
