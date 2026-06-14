# A/B Evaluation Results — sdk-generator context doc

## Pass criterion

> **Scale** if WITH-doc answers are correct and use **fewer or equal re-derivation turns** than WITHOUT, **and** total tokens do not rise (the doc's load cost is repaid). **Do not scale as-is** if WITH-doc raises tokens without cutting turns (the excess-context harm the research flagged) — then narrow the doc / drop generated blocks and re-test.

## Results table

| task | with-turns | without-turns | with-tokens (in+out) | without-tokens (in+out) | both-correct? |
|------|-----------|--------------|----------------------|-------------------------|---------------|
| 1    | —         | —            | —                    | —                       | —             |
| 2    | —         | —            | —                    | —                       | —             |
| 3    | —         | —            | —                    | —                       | —             |

## STATUS: not yet run — `claude -p` hangs in this sandbox environment

`claude` CLI is present (`claude --version` → 2.1.177) but `claude -p <prompt>
--output-format json` does not return in this environment (no API key / network
path is available for non-interactive headless invocations from a subprocess).

To obtain real results, run from a shell where `ANTHROPIC_API_KEY` is set and
`claude -p` returns promptly:

```sh
cd <repo-root>
python tools/ab_eval/run.py
```

The JSON output will be printed to stdout; paste the numbers into the table
above and record the verdict against the pass criterion.
