# Deepening the CLI command IR — design spec

> Status: **design, not yet implemented.** Captures the decisions reached in a
> grilling session on 2026-06-19, **hardened by an independent peer review**
> (verdict: GO-WITH-CHANGES; all required changes folded in below — see *Peer
> review outcome*). To be implemented later on a fresh `feature/cli-ir-deepening`
> branch off `develop` (this work is unrelated to the in-flight
> `feature/posture-product` changes and must not pile onto that branch).
>
> **Pre-flight (important):** branch from a **clean `develop`**. At spec-writing
> time the working tree carries unrelated posture/error-handling WIP that has
> already modified most of the files this design touches (`ir.py`, `classify.py`,
> `render_cli.py`, `runtime.py.jinja`, `diagnostics.py.jinja`, and several test
> files) and `.agents/context/cli-generator.md`. **All line numbers in this spec
> are indicative** (captured against `develop` at writing time; the dirty tree has
> shifted them, e.g. the `paginated` field reads `ir.py:119` on clean `develop` but
> `~:151` in the dirty tree). Re-grep on the clean branch before editing.

## Problem

`CliIR` / `Command` (`src/phantasos/generator/cli/ir.py`) is a **typed data-bag,
not a deep module**: it stores raw facts (`verb`, `object`, `variant`, `key`,
`bindings`) but exposes **no resolved behaviour**. So every consumer
re-derives the same conclusions from the raw fields, and one domain decision ends
up maintained in several places at once:

- **`Command.paginated`** (`ir.py:119`) is computed with care in `classify.py`
  (`:273`, `:353`, `:357` — initialised, set on `list`, OR-merged across merged
  bindings) and serialized into `ir.json`, but is **read nowhere in `src`**. The
  runtime re-derives the predicate inline as `binding.sub_verb == "list" and
  paginate_all` (`runtime.py.jinja:530`). Only `test_cli_classify.py:307` touches
  it. It is also the wrong granularity: the runtime cares about the *selected
  binding*, not the command. → dead field.
- **`_SUBVERB_PRIORITY`** — the binding-precedence table — is duplicated
  byte-for-byte in `render_cli.py:79` and `runtime.py.jinja:227`, with the prefix
  order in `classify.py:19` encoding the same intent a third time. The runtime
  copy **cannot be precomputed away**: `_pick_binding`’s tie-break runs over the
  candidate set that depends on which args are *present at runtime*
  (`runtime.py.jinja:233-251`). So the table must live somewhere both render-time
  and run-time can read.
- **The Typer command tree** (`typer_path`, the variant-group decision, the
  primary sub-verb) is computed in `render_cli._command_view` (`:218-227`) using a
  cross-command `variant_groups` scan (`:386`). `app.py.jinja` already *reads*
  `c.typer_path` from the view (`:39`) — it does not re-derive the path — so the
  computation lives in exactly one place today, but in the **wrong owner** (the
  render view layer) rather than the IR whose job the resolved tree is.
- **Default columns** — the `_PREFERRED` identity list + "preferred-first, cap 6"
  rule — exist as two implementations: build-time `columns.default_columns`
  (`columns.py:20-34`, over `FieldInfo`) and run-time `output._heuristic_columns`
  (`output.py.jinja:107-214`, over live row dicts). Same constant, same cap, same
  ordering rule; different inputs, so not pure duplication.

**Deletion test.** `paginated` deleted → pure shrink, nothing moves (the caller
already computes it): the canonical "stored only to be tested" tell. The tree
logic genuinely concentrates — but in `render_cli`, not the IR. → the IR is
shallow; deepening it (giving it a behavioural interface so consumers *read*
resolved values) is where the deletion test most strongly concentrates
complexity.

## The linchpin

`ir.py` imports **only** `typing` + `pydantic`. `render_cli.py:369-371` emits
`spec.py` by **copying `ir.py` verbatim**, and `runtime.py.jinja:30` does
`from .spec import CliIR, Command, Flag, MethodBinding`. Therefore **any method
or module-level constant/function added to `ir.py` automatically reaches the
runtime for free**, with no new vendored module and no dependency on the separate
"vendor runtime logic" candidate. `@property` methods are not pydantic fields, so
they are **not serialized into `ir.json`** and create **no `extra="forbid"`
round-trip risk**. This existing seam is what makes the chosen design cheap.

## Decisions (from grilling)

1. **Carrier = principled mix.** Pure per-command / per-binding resolutions become
   **methods / constants on the models in `ir.py`** (shared with the runtime via
   the `spec.py` copy). Cross-command resolutions that need sibling context (the
   Typer path) become a **stored field computed in `build_cli_ir`**, consistent
   with the existing `get_by_id_only` / `columns` / `items_field` post-passes.
2. **Columns dedup = share the constant + a ranking helper.** Put
   `PREFERRED_COLUMNS` + `MAX_COLUMNS` + a pure `rank_columns(names)` in `ir.py`
   (ships to the runtime via `spec.py`). Both call sites use it; each keeps its
   own input filtering and output shaping. (See the behaviour note below — this
   also retires a latent build-vs-runtime inconsistency.)
3. **Tests = move the surface onto the IR, prune the redundant.** Add direct tests
   on the real interface; delete the dead `paginated` assertion (the **only** test
   that needs removing — peer review confirmed there is *no* `_primary_sub_verb`
   helper test in `tests/`). Keep the `columns.default_columns` tests (real seam)
   and the emitted-package CliRunner tests (end-to-end backstop).
4. **`paginated` = delete** (field + 3 compute lines + assertion).
5. **Scope boundary.** Use the *existing* `ir.py → spec.py` verbatim seam; do
   **not** introduce a second vendored module here (that is the separate "vendor
   runtime logic as tested Python" candidate). If that candidate later lands, the
   resolution helpers could migrate to it. Honours the recorded
   anti-over-abstraction decision — this concentrates *existing* complexity only.

## Target shape

### `ir.py` additions

```python
# module-level, ships verbatim into spec.py
SUBVERB_PRIORITY: dict[str, int] = {
    "patch": 0, "put": 1, "create": 2, "update": 3, "delete": 4,
    "get": 5, "list": 6, "bulk_create": 7, "bulk_delete": 8,
}
PREFERRED_COLUMNS: tuple[str, ...] = ("id", "name", "type", "status", "state")
MAX_COLUMNS = 6


def rank_columns(names: list[str]) -> list[str]:
    """Preferred identity columns first (in PREFERRED order), then the rest in
    given order; de-duped; capped at MAX_COLUMNS. Input is the already-filtered,
    already-ordered candidate list — filtering (which fields are scalar-ish) stays
    at each call site."""
    chosen = [n for n in PREFERRED_COLUMNS if n in names]
    chosen += [n for n in names if n not in chosen]
    return chosen[:MAX_COLUMNS]


class MethodBinding(BaseModel):
    ...
    @property
    def rank(self) -> int:
        return SUBVERB_PRIORITY.get(self.sub_verb, 99)


class Command(BaseModel):
    ...
    typer_path: list[str] = []            # STORED (needs sibling context)
    # paginated: REMOVED

    @property
    def leaf(self) -> str | None:
        """Third command segment: a oneOf variant OR a request action."""
        return self.variant or self.action

    @property
    def primary_sub_verb(self) -> str:
        """Headline sub-verb for naming/grouping. Guarded for the (shouldn't-happen)
        empty-bindings case so a malformed command can't raise at render time."""
        if not self.bindings:
            return ""
        return min(self.bindings, key=lambda b: b.rank).sub_verb
```

### Consumer rewires

- **`render_cli.py`**: delete `_SUBVERB_PRIORITY`, `_primary_sub_verb`, `_leaf`;
  `_func_name` uses `c.leaf`; `_command_view` reads `c.typer_path` and drops the
  `variant_groups` parameter; delete the `variant_groups` computation (`:386`) and
  its threading (`:391`, `:411`). **Note both inline forms of the leaf concept**
  must go: the `_leaf` helper *and* the `c.variant or c.action` written directly
  into the `variant_groups` set comprehension (`:386`) — both become `c.leaf`.
- **`discover.py`** *(peer-review catch — was missed)*: `render_table` computes
  `leaf = c.variant or c.action` inline (`discover.py:11`) — a **third copy** of
  the same concept. Rewire it to `c.leaf` in commit 1, or the `leaf` dedup is
  incomplete and the locality goal is unmet.
- **`runtime.py.jinja`**: delete the local `_SUBVERB_PRIORITY` (`:227-230`);
  `_pick_binding` tie-break becomes
  `min(top, key=lambda b: (b.rank, b.sdk_method))`.
- **`classify.build_cli_ir`**: add a `typer_path` pass **at the very end of the
  function — after the columns pass** — so `groups` is fully populated, all
  `bindings` are appended (`primary_sub_verb` needs them), and `variant_groups` is
  built over the final `groups.values()` (equivalent to today's render-time set,
  which is built over `ir.commands` after the no-op `model_copy` enrichment that
  never adds/removes commands):
  ```python
  variant_groups = {(c.verb, c.object) for c in groups.values() if c.leaf}
  for cmd in groups.values():
      if cmd.leaf:
          cmd.typer_path = [cmd.object, cmd.leaf]
      elif (cmd.verb, cmd.object) in variant_groups:
          cmd.typer_path = [cmd.object, cmd.primary_sub_verb]
      else:
          cmd.typer_path = [cmd.object]
  ```
  Remove the `paginated=` kwargs (`:273`, `:353`) and the OR-merge (`:357`).
- **`columns.py`**: `default_columns` calls `rank_columns` (see behaviour note);
  imports the constants/helper from `.ir`.
- **`output.py.jinja`**: `_heuristic_columns` calls `rank_columns`; delete the
  local `_PREFERRED` / `_MAX_HEURISTIC`; add `from .spec import rank_columns`
  (matches its existing `from . import …` style).
- **`app.py.jinja`**: **unchanged** — it reads `c.typer_path` from the view dict,
  which now sources the stored field.

### Behaviour note — the json-preferred column quirk (decide deliberately)

Today `default_columns` builds `names = {f.name for f in fields}` over **all**
fields (`columns.py:27`), so a *preferred* field (`id`/`name`/`type`/`status`/
`state`) is selected **even when it is `json`-kind** (a nested object), while the
fill loop excludes non-preferred `json` fields. The runtime `_heuristic_columns`
**excludes all nested values** (`output.py.jinja:205-210`). So a model with, say,
a nested `status` object yields a `status` column at build time but not at
runtime — a latent inconsistency.

**Decision:** unify on *scalar-ish, preferred-first*. The build-time caller passes
only `scalar`/`enum` field names into `rank_columns`:

```python
def default_columns(fields: list[FieldInfo]) -> list[ColumnSpec]:
    names = [f.name for f in fields if f.kind in ("scalar", "enum")]
    return [ColumnSpec(header=n, path=n) for n in rank_columns(names)]
```

This removes the quirk (a nested `status` is no longer rendered as a flat
`json.dumps` cell). Note (peer-review correction): `rank_columns` unifies only the
**ordering + cap**, *not* the filter — build still filters on `FieldInfo.kind`
(static) and runtime still filters on live values (`isinstance(v, dict)` /
nested-list checks in `output.py.jinja`), so the two remain "agree on ordering+cap,
each keeps its own kind/value filter." It is a **micro behaviour-change in an edge
case** (an un-curated object with a nested `id`/`name`/`type`/`status`/`state`
field loses that column at build time) — flagged here and covered by a new test. (If review prefers strict
preservation, the alternative is to keep the two-tier filter in `default_columns`
and have `rank_columns` only re-order+cap; this design rejects that as carrying
the quirk forward for no benefit.)

## Implementation plan — tiny commits

Each commit is behaviour-preserving (except the flagged column edge case in
commit 4) and leaves `uv run nox -s gate` green. None of the touched files are
frozen oracles (`.claude/harness.toml` `protected_globs` covers only the
live-CRUD template, `tests/acceptance/**`, and `.claude/**`).

1. **Sub-verb precedence + `leaf` → models.** Add `SUBVERB_PRIORITY`,
   `MethodBinding.rank`, `Command.leaf`, `Command.primary_sub_verb` to `ir.py`.
   Rewire `render_cli` (`_func_name`/`_command_view`/the `variant_groups`
   comprehension via `c.leaf`/`c.primary_sub_verb`), `runtime.py.jinja`
   (`_pick_binding` via `b.rank`), **and `discover.py:render_table` (the missed
   third `leaf` copy) via `c.leaf`**. Pure dedup, no behaviour change. *Verify:*
   gate + emitted CliRunner tests + `cli discover` table output unchanged.
2. **Delete dead `paginated`.** Remove the `ir.py` field, the `classify.py`
   compute lines, and the `test_cli_classify.py:307` assertion. *Verify:* gate
   green; `grep paginated src` empty.
3. **`typer_path` → stored field.** Add the field + the `build_cli_ir` post-pass;
   simplify `_command_view` (drop `variant_groups` param + computation). `app.py`
   unchanged. *Verify:* emitted app tree identical (CliRunner registration tests).
4. **Columns → `rank_columns`.** Add `PREFERRED_COLUMNS`/`MAX_COLUMNS`/
   `rank_columns` to `ir.py`; rewire `columns.py` + `output.py.jinja` (add
   `from .spec import rank_columns`). Apply the json-preferred decision above.
   *Verify:* `test_cli_columns` + emitted table tests; add the adversarial
   `rank_columns` tests + a test pinning the unified scalar-ish behaviour. **Also
   build BOTH real products** (`uv run phantasos sdk build …` then `cli build` for
   `posture` and `prisma-browser`) and confirm no *un-curated* object loses a
   column — both products curate `columns:` in `cli.yml` for their listed objects
   (those go through `resolve_columns`, immune), so the expected impact is none;
   verify rather than assume. If any un-curated object is affected, record it
   explicitly here before merging.
5. **Test surface → IR; prune.** Add direct tests: `Command.primary_sub_verb`
   precedence, `MethodBinding.rank`, `build_cli_ir` stamps the right `typer_path`
   (`[obj]` / `[obj, leaf]` / `[obj, primary]` for variant groups), and the
   adversarial `rank_columns` cases. The **only** deletion is the dead
   `paginated` assertion (already removed in commit 2; there is no
   `_primary_sub_verb` test to delete — peer-review verified). *Verify:* gate
   green.

**Finalisation (after commit 5):** update the `.agents/context/cli-generator.md`
narrative to describe the IR's new behavioural interface, then run
`uv run nox -s context -- --check`. Open the PR with `--base develop`
(squash-merge); no version bump; record under `## [Unreleased]` in `CHANGELOG.md`.

## Tests added / removed

| Added (real-interface) | Removed / changed |
|---|---|
| `Command.primary_sub_verb` picks `patch>put>create>…` | `assert show_widget.paginated is True` (dead) — **the only removal** |
| `MethodBinding.rank` ordering | — |
| `build_cli_ir` → `cmd.typer_path` per command shape | — |
| `rank_columns`: preferred-first + cap; **adversarial on the boundary** — (a) >6 fields with all 5 preferred + extras (cap drops trailing non-preferred), (b) the de-dup branch when a name is both preferred and present | — |
| `default_columns` unified scalar-ish (the flagged edge); the two existing `test_cli_columns` cases do NOT pin the quirk, so they survive unchanged | — |
| *(keep)* `test_cli_columns.default_columns` (real seam) | |
| *(keep)* emitted CliRunner end-to-end tests | |

## Peer review outcome

Independent adversarial review (2026-06-19) — verdict **GO-WITH-CHANGES**. All
required changes are now folded into the design/plan above:

- **(was blocking) `discover.py:11` third `leaf` copy** — added to the consumer
  map and commit 1.
- **(correctness) no `_primary_sub_verb` test exists** — test plan corrected; the
  only removal is the `paginated` assertion.
- **(hardening) `rank_columns` "agree" overstatement** — softened to "ordering+cap
  only; each side keeps its own filter."
- **(hardening) `typer_path` pass position** — pinned to the end of
  `build_cli_ir`, `variant_groups` over final `groups.values()`.
- **(hardening) adversarial `rank_columns` tests** — added (cap boundary + de-dup
  branch).
- **(hardening) real-product column impact** — commit 4 now builds both products
  to verify no un-curated object loses a column.

Confirmed safe by review (no change needed): `paginated` is dead across all of
`src` (incl. `cli discover`/`docs`/`inventory`); no committed/fixture `ir.json`
would break `extra="forbid"` (all tests emit fresh); `MethodBinding.rank` resolves
in the runtime (it's imported; `candidates`/`top` are `MethodBinding` instances);
`app.py.jinja` stays byte-identical (reads the view dict's `typer_path`);
`@property` coexists cleanly with `extra="forbid"`/frozen and never serializes;
no touched file is a frozen oracle.

## Residual risks / open items

- **`primary_sub_verb` on empty bindings** — guarded to return `""`; confirmed
  belt-and-suspenders (every `build_cli_ir` path appends ≥1 binding immediately
  after construction). Non-load-bearing.
- **`spec.py` standalone-shippability** — the new constants/functions/properties
  must keep `ir.py`'s imports limited to `typing` + `pydantic` (they do).
- **Real-product un-curated columns** — the one empirically-open item; closed
  during commit 4 by building both products (see plan). Curated columns are immune
  (`resolve_columns`); only an un-curated object with a nested
  id/name/type/status/state field could change.
- **Branch hygiene** — implement off a **clean `develop`**, not the current dirty
  tree (see Pre-flight). Re-grep line numbers there.
