# Agent-facing technical context docs (`.agents/context/`) — Design

**Date:** 2026-06-14
**Status:** Design grilled with user + **deep-research-validated and revised** (this is v2; see *Deep-research validation outcome*). Ready for the implementation plan.
**Scope:** A net-new, deeply technical documentation set for in-repo coding agents, living in `.agents/context/`. This is **Set 2 only** — the user-facing mkdocs rework (**Set 1**) is a separate follow-up (see *Out of scope*).

## Motivation & evidence posture

phantasos is a code-generation toolchain whose design rationale and architecture are spread across 14 specs, 25 plans, a stale `docs/ARCHITECTURE.md`, and the code itself. An agent (Claude Code) working in-repo has no single, current, high-signal place to understand *what the system is*, *how each subsystem works*, and *why* the key decisions were made — so it re-derives context every session and risks acting on stale narrative.

`docs/ARCHITECTURE.md` is the cautionary tale: it opens *"Status: proposal (no refactor yet)"* and describes a `phantasos/` package that the code long ago replaced with `src/phantasos/generator/{sdk,cli}` + a whole CLI-generator subsystem the doc never mentions. Documentation that isn't tied to code changes rots.

**Evidence posture (deep-research-validated — read this before justifying the effort).** We do **not** claim these docs *measurably improve* agent task success. That claim is unsupported by primary research and is actively challenged: a controlled study (Gloaguen et al., arXiv:2602.11988, Feb 2026) found **excess/unnecessary** repository context can *reduce* success and raise cost >20%, and the headline "AGENTS.md → 28.6% faster" result (arXiv:2601.20404) failed adversarial verification. The only robust empirical finding is that **verbose context hurts**. Therefore the goal is narrow and defensible:

- **Reduce per-session re-derivation** — give the agent one current, high-signal place instead of re-reading scattered specs/code each session.
- **Avoid stale-narrative harm** — kill the `ARCHITECTURE.md` failure mode via freshness-first design (generate what can rot; gate the rest).

Because excess context is the proven risk, **ruthless minimalism is a hard constraint, not a nicety** — and we **measure** the effect rather than assume it (see *Validation*).

## Decisions (user-confirmed)

| # | Topic | Decision |
|---|---|---|
| 1 | Primary consumer | An **in-repo coding agent** (Claude Code). Optimize for *current, actionable, architecturally accurate*; low staleness tolerance. |
| 2 | Content | Leads with the **WHAT** — an overarching system-level technical design **plus** per-subsystem deep-dives. The **WHY** (decisions, goals/non-goals) sits **alongside, not instead**. |
| 3 | WHAT sourcing | From the specs/plans, **validated against code** (execute where feasible, trace otherwise, mark static-only claims). |
| 4 | WHY sourcing | Distill from the written record (specs/plans/commits/code), then a **targeted interview** to fill high-value unwritten gaps. |
| 5 | Structure | **Modular, by subsystem.** A short index an agent reads first → per-subsystem deep-dives mirroring the code → cross-cutting decisions + goals/non-goals. |
| 6 | Location & mechanism | **`.agents/context/`** (top-level, machine-facing), **plain markdown files** — *not* native Agent Skills. (Skills were considered; we apply the progressive-disclosure *principle* but keep files: they double as human-readable dev reference, fit the file-oriented gate + generator, and explicit "read the doc for the subsystem you're editing" is more deterministic than description-triggered skill invocation.) |
| 7 | Entry pointers | **CLAUDE.md** (Claude, always-loaded) **+ a thin root `AGENTS.md`** both point at the index via a **plain-path instruction** — explicitly **NOT a `@`-import** (an `@`-import loads at launch and would silently turn the on-demand design into preload-everything). |
| 8 | Depth & altitude | **Symbol-level anchors used as NAVIGATION aids** — name the key class/function and *which file to open*, not an exhaustive enumeration; short excerpts only where they clarify; **no line numbers**. Each deep-dive also carries **build/run pointers** for its subsystem (the most common real-world manifest category). |
| 9 | CLAUDE.md split | **Rules stay normative in CLAUDE.md** (always-loaded); context docs carry **mechanism + rationale** (on-demand), cross-linked. One home per fact — no copied rules. |
| 10 | Freshness mechanisms | Three composed: (a) CLAUDE.md instructs agents to **read + update** the relevant doc; (b) the **harness gate enforces** it (**strongly, not absolutely** — see below); (c) **mechanical sections are generated** (module map, public signatures, config tables, CLI list), kept **terse**. **No** scheduled re-validation agent. |
| 11 | Gate dependency | The freshness gate is an **extension of the harness fast-gate hook** (`.claude/hooks/fast_gate.py`). The harness **landed on `develop` 2026-06-14** (PR #10, squash `08a1769`), so the dependency is **satisfied** — the gate increment builds directly on the fast-gate hook + `.claude/harness.toml`. |
| 12 | Scope of effort | **Set 2 only.** Set 1 (user-facing mkdocs, incl. replacing `ARCHITECTURE.md`) is a separate follow-up. |
| 13 | Anti-bloat constraint | **Minimalism is enforced, not aspirational.** Per-doc **soft size cap** (see *Open questions* for the number); generated blocks limited to **signature + one docstring line**; nothing file-by-file or API-dump-heavy ever enters CLAUDE.md; a loaded subsystem doc must stay small enough to not provoke context rot. |
| 14 | De-risk by measurement | Build is **staged with an explicit A/B check**: a small internal task set run **with vs. without** the docs, tracking re-derivation turns / tokens (and watching for the excess-context *harm* the research flags), to answer the validation gate with data before scaling to all 11 docs + the gate. |

## The doc set

```
.agents/
  context/
    index.md              # read-first: overarching system technical design + curated link index
    product-config.md     # products/<name>/ anatomy + productconfig.py loading/validation
    sdk-generator.md      # SDK build pipeline: preprocess→provision(JRE/jar)→OAG→patches→vendor→scaffold→smoke
    components.md         # vendored+templated component model: auth/pagination/errors/retry/facade
    cli-generator.md      # CLI-from-SDK: _generated vs custom templates, cli_overrides, layered config
    scaffold.md           # scaffold engine: built-in templates vs product overrides, same-path-wins, gated tests
    phantasos-cli.md      # phantasos's own Typer command surface (cli.py) + its own config (config.py)
    harness-and-testing.md# mechanism+WHY of the test/quality harness (rules live in CLAUDE.md)
    release-workflow.md   # mechanism+WHY of branching/release automation (rules live in CLAUDE.md)
    decisions.md          # design-decision log / rationale (the WHY)
    goals-non-goals.md    # what phantasos is and isn't (the WHY)
AGENTS.md                 # NEW thin root pointer → .agents/context/index.md (plain path, not @-import)
CLAUDE.md                 # EDIT: plain-path pointer + the read-before / update-after instruction
```

11 docs: 7 subsystem + harness-and-testing + release-workflow (mechanism/WHY; rules stay in CLAUDE.md) + decisions + goals-non-goals. Subsystem names validated against the real `src/phantasos/` layout. (Per decision 14 the *build order* is staged — a thin slice first, not all 11 at once.)

### `index.md` — the read-first doc (llms.txt-shaped)

Follows the llms.txt structure (H1 + one-blockquote summary + H2 sections of curated links) — the most parseable, lowest-token "map" format, matching the just-in-time principle: an agent reads the index, then loads only the relevant deep-dive.

1. **H1** `phantasos` + one-blockquote summary of what it is.
2. **Overarching technical design (the WHAT, substantive — not a thin map):** the `spec → SDK → CLI` two-stage pipeline end to end; the three-layer mental model (**framework code** vs **generated artifact** vs **product config**); the control/data flow; the repo map; the hard invariants (e.g. *"the generated SDK is a pure build artifact — never hand-edit"*). Kept tight (see size cap).
3. **H2 Subsystem deep-dives** — curated links: `- [sdk-generator](sdk-generator.md): <one line>` per doc (the lightweight-identifier index).
4. **H2 Cross-cutting** — links to `decisions.md`, `goals-non-goals.md`.
5. **Pointer to CLAUDE.md** as the source of the binding *rules*.

### Per-subsystem deep-dive anatomy (uniform template)

Each subsystem doc has the same shape so an agent (and the gate/generator) can rely on it, and **stays under the size cap**:

1. **Provenance stamp** (top): `Validated against <git-sha> on <date>` + one-line purpose.
2. **Purpose & responsibilities** — hand-written WHAT, terse.
3. **How it works** — data flow / pipeline call chain, with **symbol-level navigation anchors** (key class/function names + the file to open). Hand-written, right-altitude — *navigate, don't enumerate*.
4. **Build/run pointers** — how to build/run/test just this subsystem (commands, the relevant `nox` session). (Highest-value real-world category; cheap to keep.)
5. **`<!-- GENERATED -->` blocks** — module/file map; public API signatures (signature + one docstring line only); config-field tables; CLI command list (whichever apply). Marker-delimited, regenerated by tooling; **terse**.
6. **Gotchas / invariants** — hand-written.
7. **See also** — links to the relevant specs/plans (provenance), `decisions.md` entries, and any binding CLAUDE.md rule.

## Freshness mechanisms (detail)

### (a) CLAUDE.md instruction (plain-path, not `@`-import)
A new CLAUDE.md section instructs agents to **read** the relevant `.agents/context/` doc before working in a subsystem and **update** it (narrative) + **regenerate** it (mechanical) as part of any change that alters that subsystem. The pointer is a **plain instruction/path** so the docs load on demand — an `@`-import would load them at launch and defeat the entire on-demand design. Keep references **one hop deep**.

### (b) Harness-gate enforcement (extends the fast-gate hook) — strongly enforced, not absolute
- A new mapping in `.claude/harness.toml`, e.g. `[context_docs]`, from a code glob to its owning doc:

  | Code path (glob) | Owning doc |
  |---|---|
  | `src/phantasos/generator/sdk/**` (excl. `components/`) | `sdk-generator.md` |
  | `src/phantasos/generator/sdk/components/**` | `components.md` |
  | `src/phantasos/generator/cli/**` | `cli-generator.md` |
  | `src/phantasos/scaffold.py`, `src/phantasos/scaffold/**` | `scaffold.md` |
  | `src/phantasos/productconfig.py`, `products/**` (config) | `product-config.md` |
  | `src/phantasos/cli.py`, `src/phantasos/config.py` | `phantasos-cli.md` |
  | `noxfile.py`, `.claude/harness.toml`, `.claude/hooks/**` | `harness-and-testing.md` |
  | release workflow / version / CHANGELOG flow | `release-workflow.md` |

- The fast-gate (Stop) hook, after its existing checks, verifies: for each changed code glob in the diff, its owning doc is **also** in the diff **and** its generated blocks are current (regenerate-and-`--check` produces no diff). `index.md`/`decisions.md`/`goals-non-goals.md` are **not** auto-gated (judgment-based, cross-cutting) but are flagged on architectural-shaped changes.
- **Posture: warn loudly first, escalate to block** — and a `context_docs_enabled` toggle. This is **strongly enforced, not absolutely binding**: Claude Code overrides a Stop hook and ends the turn **after 8 consecutive blocks** (so the gate cannot *guarantee* an update — it raises the cost of skipping, backed by CODEOWNERS/CI as the harder net). Inherit the harness's fail-open + loop-guard philosophy.

### (c) Generated mechanical sections — terse, and they must earn their keep vs `grep`
- A generator (a `nox -s context` session wrapping a script under e.g. `tools/`) writes mechanical content into `<!-- GENERATED:<kind> -->` … `<!-- /GENERATED -->` markers, idempotently: module/file map; public API signatures (signature + one docstring line); config-field tables (introspect the pydantic models — host `config.py`; the CLI generator's `config.py.jinja`); CLI command list (introspect the host Typer app).
- A `--check` mode (regenerate to a buffer, diff against the file) is **mandatory** — it gives the gate a deterministic "generated sections current?" signal and makes generated content unable to rot.
- **Caveat (research):** Anthropic dropped vector-DB RAG for Claude Code because indexes go stale and agentic `grep` over code wins. So a generated module/signature block **competes with the agent just grepping** — its value is **curation** (what matters, in one place), not raw enumeration. Keep blocks terse; the A/B step (decision 14) tests their marginal value before we over-invest in the generator. Generated-CLI surfaces are per-product/dynamic and **out of scope** (these docs describe the *generator*).

## Deep-research validation outcome (2026-06-14)

A deep-research pass (104 agents, 22 sources, 25 claims adversarially verified — 18 confirmed, 7 refuted) validated v1 and drove this v2. Summary of what changed:

| Finding (confidence) | Change made |
|---|---|
| Core architecture (modular, on-demand, referenced-not-preloaded, llms.txt index) is endorsed by Anthropic (**high**, 3-0) | Kept as-is. |
| "Docs measurably improve performance" is unsupported; excess context can *hurt* (**high**, 3-0; arXiv:2602.11988, refuted arXiv:2601.20404) | Rewrote Motivation → *reduce re-derivation / avoid stale-narrative harm*; added decision 14 (measure it). |
| Context rot; exclude file-by-file/API dumps from CLAUDE.md (**high**, 3-0) | Added decision 13 (anti-bloat + size cap); generated blocks terse, on-demand only. |
| `@`-import loads at launch, defeats on-demand (**high**) | Decision 7: plain-path pointer, explicitly not `@`-import. |
| Stop hook overridden after 8 consecutive blocks (**high**, 3-0) | Mechanism (b): "strongly enforced, not absolute"; dropped "binding". |
| Symbol-level depth not directly evidenced; over-specification is the real risk; build/run is the top real-world category (**medium**, 2-1) | Decision 8: anchors = navigation aids; added build/run pointers to the template. |
| Agentic `grep` beat the stale code index Anthropic dropped (**medium**, 3-0) | Mechanism (c): generated blocks justified by curation; A/B tests marginal value. |

Key sources: [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), [Claude Code best practices](https://code.claude.com/docs/en/best-practices), [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), [Gloaguen et al. arXiv:2602.11988](https://arxiv.org/abs/2602.11988), [arXiv:2509.14744](https://arxiv.org/pdf/2509.14744), [Chroma context-rot](https://www.trychroma.com/research/context-rot).

## Sequencing & dependencies

1. **Harness dependency — satisfied:** the autonomous-harness thin slice landed on `develop` 2026-06-14 (PR #10, squash `08a1769`). `.claude/hooks/fast_gate.py`, `.claude/harness.toml`, and `nox -s gate`/`live` now exist, so the gate extension (mechanism b) builds directly on them.
2. **Staged build (decisions 13–14):** **(slice)** `index.md` + 1–2 subsystem deep-dives + the generator + the plain-path pointers → **A/B evaluate** (re-derivation turns/tokens, with-vs-without; watch for excess-context harm) → **(scale)** remaining deep-dives + decisions/goals-non-goals → **(gate)** the harness gate extension last, once the docs it enforces exist and proved their worth.
3. Overall plan order: focused research *(done)* → spec *(done)* → deep-research validation *(done)* → **implementation plan** → staged build.

## Validation

Two layers:

- **Doc-accuracy** (per CLAUDE.md *evidence-before-assertions*): trace call chains statically for structure/symbols; run the command/test and observe for behavioral claims where the environment allows (`nox -s gate`/`tests`, a real `phantasos sdk build`); **mark** claims confirmable only statically here (live-tenant paths, the Java/network JRE+jar fetch).
- **Effect (A/B, decision 14):** a small internal task set executed **with and without** the docs available, measuring re-derivation turns and token cost, to confirm the docs help (or at least don't *hurt* per the excess-context evidence) before scaling. Defines what "the docs are worth it" means in numbers.

## Open questions (for the plan)

- **Per-doc size cap number.** No authoritative anchor exists (Anthropic's 100/5k/unlimited tiers were *refuted* 0-3). The plan must pick + justify one (working proposal: index ≤ ~1 screen; each subsystem doc ≤ ~300–500 lines incl. generated blocks).
- **A/B harness specifics:** the task set, the with/without conditions, and the metric (re-derivation turns vs tokens vs both).
- **Generated-block marginal value vs `grep`:** measure before over-investing in the generator; possibly ship narrative-only deep-dives first and add generation only where curation clearly beats grep.
- Gate **block-vs-warn** strictness + `context_docs_enabled` semantics; generator host/location + marker syntax.
- The targeted WHY-interview question list (e.g. YAML `sdk.yml` vs the `ARCHITECTURE.md` Python-module config; why these five components; deliberate non-goals).

## Out of scope

- **Set 1** — the user-facing mkdocs rework, including replacing `docs/ARCHITECTURE.md` with a simplified architecture page. Separate follow-up; the boundary is recorded so the two efforts don't duplicate.
- **Native Agent Skills** as the mechanism (considered; chose file-based `.agents/context/` — decision 6).
- A **scheduled re-validation agent** (considered, rejected — PR noise + cost).
- Documenting any **specific generated CLI/SDK's** surface (dynamic, per-product).
- Migrating, archiving, or rewriting the existing specs/plans — they remain the continuous-delivery record and are mined, not absorbed.
