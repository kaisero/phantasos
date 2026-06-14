# A/B Evaluation Results — sdk-generator context doc

## Pass criterion

> **Scale** if WITH-doc answers are correct and use **fewer or equal re-derivation turns** than WITHOUT, **and** total tokens do not rise (the doc's load cost is repaid). **Do not scale as-is** if WITH-doc raises tokens without cutting turns (the excess-context harm the research flagged) — then narrow the doc / drop generated blocks and re-test.

## Run

- Date: 2026-06-14 · Model: `claude-opus-4-8` · `claude -p --output-format json` from repo root.
- Conditions: **with** = `.agents/context/sdk-generator.md` present; **without** = doc renamed aside (agent derives from code).
- Tokens = input + output per run. Single run per cell (n=1 per condition per task).

## Results table

| task | with-turns | without-turns | with-tokens (in+out) | without-tokens (in+out) | both-correct? |
|------|-----------|--------------|----------------------|-------------------------|---------------|
| 1    | 2         | 8            | 8,105                | 9,071                   | yes           |
| 2    | 4         | 4            | 8,568                | 9,573                   | yes           |
| 3    | 5         | 3            | 8,919                | 10,563                  | yes           |
| **Σ**| **11**    | **15**       | **25,592**           | **29,207**              | **3/3**       |

(Per-task out-tokens — with vs without: T1 1306/2137, T2 1767/2361, T3 1928/3764.)

## Verdict: **PASS → scale** (directional, small-n)

- **Correctness:** 3/3 correct in BOTH conditions (the agent can derive these from code; the doc didn't change correctness).
- **Re-derivation turns:** aggregate **11 (with) ≤ 15 (without)** ✓. Strong on T1 (2 vs 8); tie on T2; **inverted on T3 (5 vs 3)**.
- **Tokens:** total **25,592 (with) < 29,207 (without)** ✓ — ~12% lower; with-doc was lower on every task's output tokens. The doc's load cost is repaid.

Meets the pass criterion on the aggregate (fewer turns AND lower tokens, no correctness loss). **Recommend scaling** to the remaining deep-dives.

### Caveats
- **Small sample:** 3 tasks, 1 run each — directional, not statistically robust. T3's turn count rose with the doc (though its tokens fell), so the turn signal is noisy. A larger task set / repeated runs would firm this up.
- **Task selection bias:** all three questions target exactly what `sdk-generator.md` documents; broader/unrelated tasks would test whether the doc ever *adds* cost without benefit.

### Doc-gap surfaced by the run (follow-up)
The "without" runs independently verified the code and flagged that `sdk-generator.md`'s Gotchas list of suppressed OAG files **omits `test-requirements.txt` and `git_push.sh`** (both in `generate.py`'s `_OAG_IGNORE`). Fix when scaling (or sooner). Also: `build.py`'s module docstring summarizes the pipeline without the provenance + smoke stages — a code-side nit, not a doc one.
