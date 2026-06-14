# oneOf Discriminator Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generated SDKs dispatch oneOf deserialization on the spec's `discriminator` mapping (`useOneOfDiscriminatorLookup=true`), fixing every `ApplicationItem` deserializing as `CustomApplication`.

**Architecture:** A new `generator:` block in `sdk.yml` (validated by a `GeneratorConfig` pydantic model) carries OpenAPI-Generator invocation options — the existing `library` knob migrates into it, and a new `oneof_discriminator_lookup: bool = True` opt-out controls the flag. `generate.generate()` threads the flag into `--additional-properties`. Everything else is verification: a permanent gated real-SDK test locks in correct variant dispatch; one-time diffs prove adem is untouched and prisma's delta is scoped to oneOf wrappers; a **user checkpoint** decides drift policy after observing what the regenerated code does with unknown discriminator values; the CLI is rebuilt and live-verified.

**Tech Stack:** Python 3.11+, pydantic v2, OpenAPI Generator 7.22.0 (pinned jar), pytest, uv.

---

## Background (read before Task 1)

**The bug (live-verified 2026-06-11):** `prisma_browser/models/application_item.py` has an *empty* `discriminator_value_class_map` and a `from_json` that trial-deserializes variants in oneOf-declaration order. Phantasos's own `patch_oneof_first_match` (`src/phantasos/patches.py:108`) rewrites it to return on first success, and `LenientStrEnum` (`patches.py:44`) makes the wrong first match *succeed with a warning* instead of being rejected — so every application payload (catalog, private, non-web) comes back typed `CustomApplication`, with variant-specific fields demoted to `additional_properties`.

**The fix:** OAG's opt-in `useOneOfDiscriminatorLookup=true` makes the generated `from_json` dispatch directly on `payload["type"]` via the spec's discriminator mapping. The spec is already correct (`ApplicationItem` declares a full `discriminator.mapping` — `products/prisma-browser/openapi.yml:5285`).

**Scope guards (grilled decisions, 2026-06-11):**
- Flag only. The residual class — *undiscriminated* oneOfs (all 11 in adem, ~3 in prisma) keep trial-deser + leniency mis-typing — is recorded in `docs/TODO.md`, not fixed.
- `generator:` block with opt-out, default **true**; `library` hard-migrates in (nothing in `products/` sets it; no alias).
- Branch: `cli-generator`. Drift policy: **verify-then-decide** (Task 7 checkpoint). CLI: re-verify + repair only; column enhancements go to the roadmap.

**Process notes:**
- Run everything from `/home/ubuntu/git/phantasos` with `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` (repo `.venv` is on sshfs and can't hold symlinks).
- Subagents must NOT `git checkout`/`switch`/`reset`. Commit on `cli-generator`.
- Sibling repos `/home/ubuntu/git/prisma-browser-sdk` and `/home/ubuntu/git/prisma-browser-cli` get regenerated output; do NOT commit them — flag their dirty state in the handoff.
- Suite baseline: 238 passed, ruff + mypy clean.

## File Structure

| File | Change |
|------|--------|
| `src/phantasos/productconfig.py` | New `GeneratorConfig` model; `ProductConfig.library` → `ProductConfig.generator`; context wiring |
| `src/phantasos/generate.py` | `generate()` gains `oneof_discriminator_lookup: bool = True`, threads it into `--additional-properties` |
| `src/phantasos/__init__.py` | `build()` call site passes both generator options from `cfg.generator` |
| `tests/test_productconfig.py` | Generator-block tests; update `cfg.library` assertion |
| `tests/test_generate.py` | Flag-threading test |
| `tests/test_cli.py` | Update two `fake_generate` signatures (lines ~29, ~138) |
| `tests/test_sdk_oneof_real.py` | NEW — permanent gated variant-dispatch test |
| `docs/AUTHORING_A_SPEC.md` | `generator:` section; remove top-level `library` row |
| `docs/TODO.md` | Residual undiscriminated-oneOf entry |

---

### Task 1: `generator:` block in ProductConfig

**Files:**
- Modify: `src/phantasos/productconfig.py` (model ~line 64, context line 188)
- Test: `tests/test_productconfig.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_productconfig.py` (imports of `ProductConfig`, `pytest`, `ValidationError` already exist):

```python
def test_generator_block_defaults() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.generator.library == "urllib3"
    assert cfg.generator.oneof_discriminator_lookup is True


def test_generator_block_overrides() -> None:
    cfg = ProductConfig.model_validate(
        {
            "package": "acme",
            "output": "../acme-sdk",
            "base_url": "https://api/",
            "generator": {"library": "httpx", "oneof_discriminator_lookup": False},
        }
    )
    assert cfg.generator.library == "httpx"
    assert cfg.generator.oneof_discriminator_lookup is False


def test_top_level_library_rejected() -> None:
    # `library` migrated into the generator: block (2026-06-11); extra=forbid rejects it
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {"package": "a", "output": "o", "base_url": "b", "library": "httpx"}
        )
```

Also update the existing assertion in `test_productconfig_minimal` (line 21):

```python
    assert cfg.generator.library == "urllib3"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_productconfig.py -x -q`
Expected: FAIL — `AttributeError: 'ProductConfig' object has no attribute 'generator'`

- [ ] **Step 3: Implement**

In `src/phantasos/productconfig.py`, add above `ProductConfig`:

```python
class GeneratorConfig(BaseModel):
    """OpenAPI Generator invocation options (sdk.yml `generator:` block)."""

    model_config = ConfigDict(extra="forbid")
    library: str = "urllib3"
    oneof_discriminator_lookup: bool = True
```

In `ProductConfig`, replace `library: str = "urllib3"` (line 69) with:

```python
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
```

In `load_product`'s context dict (line 188), replace `"library": cfg.library,` with:

```python
        "library": cfg.generator.library,
```

(The `library` *context key* is template-facing and stays — `_AUTO_EXPOSED` unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_productconfig.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(sdk-config): generator: block — library migrates in, oneof_discriminator_lookup opt-out (default true)"
```

---

### Task 2: Thread the flag through `generate.generate()`

**Files:**
- Modify: `src/phantasos/generate.py:62-87`, `src/phantasos/__init__.py:72`
- Test: `tests/test_generate.py`, `tests/test_cli.py` (two fake signatures)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_generate.py`:

```python
def test_generate_passes_discriminator_lookup_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("phantasos.provision.resolve_java", lambda: Path("/fake/java"))
    monkeypatch.setattr(generate, "ensure_jar", lambda: tmp_path / "oag.jar")
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kw: object) -> object:
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr("phantasos.generate.subprocess.run", fake_run)

    generate.generate("spec.yaml", str(tmp_path), "pkg")
    props = captured["cmd"][captured["cmd"].index("--additional-properties") + 1]
    assert "useOneOfDiscriminatorLookup=true" in props

    generate.generate(
        "spec.yaml", str(tmp_path), "pkg", oneof_discriminator_lookup=False
    )
    props = captured["cmd"][captured["cmd"].index("--additional-properties") + 1]
    assert "useOneOfDiscriminatorLookup=false" in props
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_generate.py::test_generate_passes_discriminator_lookup_flag -x -q`
Expected: FAIL — `AssertionError` (flag absent), then `TypeError` on the kwarg

- [ ] **Step 3: Implement**

In `src/phantasos/generate.py`, change the `generate` signature and properties string:

```python
def generate(
    spec_path: str,
    out_dir: str,
    package: str,
    library: str = "urllib3",
    oneof_discriminator_lookup: bool = True,
) -> None:
    java = provision.resolve_java()
    jar = ensure_jar()
    lookup = "true" if oneof_discriminator_lookup else "false"
    cmd = [
        str(java),
        "-jar",
        str(jar),
        "generate",
        "-g",
        "python",
        "-i",
        spec_path,
        "-o",
        out_dir,
        "--package-name",
        package,
        "--additional-properties",
        f"library={library},disallowAdditionalPropertiesIfNotPresent=false,"
        f"useOneOfDiscriminatorLookup={lookup}",
        "--global-property",
        "modelDocs=false,apiDocs=false,modelTests=false,apiTests=false",
        "--inline-schema-options",
        "RESOLVE_INLINE_ENUMS=true",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
```

In `src/phantasos/__init__.py:72`, change the call site:

```python
    generate.generate(
        str(pp_path),
        str(project_dir),
        cfg.package,
        library=cfg.generator.library,
        oneof_discriminator_lookup=cfg.generator.oneof_discriminator_lookup,
    )
```

In `tests/test_cli.py`, update BOTH `fake_generate` definitions (lines ~29 and ~138) to accept the new kwarg:

```python
    def fake_generate(
        spec_path: str,
        out_dir: str,
        package: str,
        library: str = "urllib3",
        oneof_discriminator_lookup: bool = True,
    ) -> None:
```

(Keep each function's existing body unchanged.)

- [ ] **Step 4: Run the affected suites**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_generate.py tests/test_cli.py tests/test_productconfig.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generate.py src/phantasos/__init__.py tests/test_generate.py tests/test_cli.py
git commit -m "feat(generate): pass useOneOfDiscriminatorLookup to OAG from generator config"
```

---

### Task 3: Documentation + residual TODO

**Files:**
- Modify: `docs/AUTHORING_A_SPEC.md` (build-config table ~line 25; new section after the table)
- Modify: `docs/TODO.md` (append entry)

- [ ] **Step 1: Update the build-config fields table**

In `docs/AUTHORING_A_SPEC.md`, replace the row

```
| `library` | string | `"urllib3"` | OpenAPI Generator HTTP library (`urllib3` or `httpx`) |
```

with

```
| `generator` | block | see below | OpenAPI Generator invocation options (`generator:` section) |
```

- [ ] **Step 2: Add the `generator:` section**

Insert directly after the build-config fields table (before `## Components`):

```markdown
## `generator:`

Options passed to the OpenAPI Generator invocation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `library` | string | `"urllib3"` | OpenAPI Generator HTTP library (`urllib3` or `httpx`) |
| `oneof_discriminator_lookup` | bool | `true` | Dispatch oneOf deserialization via the spec's `discriminator` mapping (OAG `useOneOfDiscriminatorLookup`). Without it, oneOf payloads resolve by trial deserialization, which mis-types variants once enums are lenient. Disable only for a spec whose discriminator mapping is wrong. |

```yaml
generator:
  library: urllib3
  oneof_discriminator_lookup: true
```

No-op for specs without `discriminator` blocks (e.g. adem) — those keep trial
deserialization.
```

(Note: `library` was a top-level field before 2026-06-11; it now lives only here.)

- [ ] **Step 3: Record the residual bug class in TODO.md**

Append to `docs/TODO.md`:

```markdown
## Undiscriminated oneOf × lenient enums — wrong-variant deserialization

`useOneOfDiscriminatorLookup=true` (2026-06-11) fixes oneOf variant dispatch only for
schemas that declare a `discriminator`. Undiscriminated oneOfs (all 11 in adem, ~3 in
prisma-browser) still use trial deserialization patched to first-match
(`patches.patch_oneof_first_match`), and `LenientStrEnum` makes a wrong first match
succeed silently — the exact mechanism behind the ApplicationItem bug. Candidate
fixes: add discriminators via spec preprocess transforms where a suitable property
exists, or make enum leniency strict during oneOf trial deserialization (fragile —
analyzed 2026-06-11, see plans/2026-06-11-oneof-discriminator-lookup.md).
```

- [ ] **Step 4: Commit**

```bash
git add docs/AUTHORING_A_SPEC.md docs/TODO.md
git commit -m "docs: generator: block reference + residual undiscriminated-oneOf TODO"
```

---

### Task 4: Permanent gated variant-dispatch test (red first)

**Files:**
- Create: `tests/test_sdk_oneof_real.py`

This test is written BEFORE the SDK rebuild — it must FAIL against the stale sibling SDK (every payload → `CustomApplication`), proving it detects the bug. Task 5's rebuild turns it green.

- [ ] **Step 1: Write the test file**

```python
"""Gated real-SDK test: oneOf discriminator dispatch picks the right variant.

Requires the sibling ../prisma-browser-sdk to be built (with the default
useOneOfDiscriminatorLookup=true). Locks in the 2026-06-11 fix for every
ApplicationItem deserializing as CustomApplication (trial-deser first-match
+ LenientStrEnum interaction).
"""

import sys
from pathlib import Path

import pytest

REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

_BASE = {
    "id": "app-0001",
    "name": "phx-test-app",
    "metadata": {
        "createdTime": "2026-01-01T00:00:00Z",
        "lastUpdatedTime": "2026-01-01T00:00:00Z",
    },
    "urls": ["*.example.com"],
}


@pytest.fixture
def application_item():
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    sys.path.insert(0, str(REAL_SDK))
    try:
        try:
            from prisma_browser.models.application_item import ApplicationItem
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        yield ApplicationItem
    finally:
        sys.path.remove(str(REAL_SDK))


@pytest.mark.parametrize(
    ("type_value", "expected_class"),
    [
        ("catalog", "CatalogApplication"),
        ("custom", "CustomApplication"),
        ("private", "PrivateApplication"),
        ("non-web", "NonWebApplication"),
    ],
)
def test_discriminator_picks_correct_variant(
    application_item, type_value, expected_class
):
    item = application_item.from_dict({**_BASE, "type": type_value})
    assert type(item.actual_instance).__name__ == expected_class


def test_catalog_fields_are_typed_not_demoted(application_item):
    item = application_item.from_dict(
        {**_BASE, "type": "catalog", "catalog_name": "ssl"}
    )
    inst = item.actual_instance
    assert inst.catalog_name == "ssl"
    assert "catalog_name" not in inst.additional_properties
```

- [ ] **Step 2: Run to verify it fails for the right reason**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_sdk_oneof_real.py -q`
Expected: 4 FAIL (catalog/private/non-web mis-typed as `CustomApplication`; the demotion test fails too), `custom` PASSES. If everything SKIPS, the sibling SDK is missing — stop and report.

- [ ] **Step 3: Commit (red is expected and documented)**

```bash
git add tests/test_sdk_oneof_real.py
git commit -m "test(gated): oneOf variant dispatch against real SDK — red until rebuild"
```

---

### Task 5: Rebuild prisma SDK → test green; inspect the delta

**Files:**
- Regenerates: `/home/ubuntu/git/prisma-browser-sdk` (sibling repo — do not commit it)

- [ ] **Step 1: Rebuild**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos build prisma-browser
```

Expected: `built prisma_browser: imported N modules, 0 failures; operations: 95` (smoke passes).

- [ ] **Step 2: Inspect the regenerated wrapper**

```bash
grep -n "_data_type\|discriminator_value_class_map" /home/ubuntu/git/prisma-browser-sdk/prisma_browser/models/application_item.py | head
```

Expected: `from_json` now reads the discriminator (a `json.loads(json_str).get("type")`-style lookup) and/or `discriminator_value_class_map` is populated with the 5 spec mappings. Record the exact emitted shape in the task report — Task 7's checkpoint needs it.

Also confirm the phantasos patches still applied cleanly (lenient enums + first-match on any remaining trial loops):

```bash
grep -rn "LenientStrEnum" /home/ubuntu/git/prisma-browser-sdk/prisma_browser/models/application_type_input.py | head -2
```

Expected: enum still rebased onto `LenientStrEnum`.

- [ ] **Step 3: Gated test goes green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_sdk_oneof_real.py -q`
Expected: 5 passed.

- [ ] **Step 4: Full suite still green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q`
Expected: 246 passed (238 baseline + 3 productconfig + 1 generate + 5 oneOf, minus 1 changed assertion — count may differ slightly; zero failures is the requirement). The other real-SDK tests (`test_cli_emitted_real.py`) must also pass against the rebuilt SDK.

- [ ] **Step 5: Commit (phantasos repo only)**

Nothing in phantasos changed in this task; commit only if Step 2 revealed something requiring a code tweak. Otherwise note "no phantasos changes" and move on.

---

### Task 6: One-time no-op / blast-radius diff proofs

**Files:** none (verification only; results go in the task report)

- [ ] **Step 1: adem no-op proof**

adem's spec has 11 oneOfs and ZERO discriminators — output must be byte-identical with the flag on and off. Use the raw spec (preprocessing doesn't touch discriminators); if OAG rejects the raw spec, first run `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos build adem --no-smoke` and use `/home/ubuntu/git/adem-sdk/.phantasos/preprocessed.yaml` instead.

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run python - <<'EOF'
from phantasos import generate
for flag, dest in [(False, "/tmp/oneof-diff/adem-off"), (True, "/tmp/oneof-diff/adem-on")]:
    generate.generate("products/adem/openapi.yml", dest, "adem",
                      oneof_discriminator_lookup=flag)
EOF
diff -r /tmp/oneof-diff/adem-off/adem /tmp/oneof-diff/adem-on/adem && echo "ADEM: IDENTICAL"
```

Expected: `ADEM: IDENTICAL`. If there IS a diff, stop and report it verbatim — that breaks the "no-op without discriminators" assumption and the user must see it.

- [ ] **Step 2: prisma blast-radius proof**

```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run python - <<'EOF'
from phantasos import generate
for flag, dest in [(False, "/tmp/oneof-diff/pb-off"), (True, "/tmp/oneof-diff/pb-on")]:
    generate.generate("/home/ubuntu/git/prisma-browser-sdk/.phantasos/preprocessed.yaml",
                      dest, "prisma_browser", oneof_discriminator_lookup=flag)
EOF
diff -rq /tmp/oneof-diff/pb-off/prisma_browser /tmp/oneof-diff/pb-on/prisma_browser
```

Expected: differing files are ONLY oneOf wrapper models whose schema has a discriminator (e.g. `application_item.py`; list every file and check each against the spec's 6 discriminator blocks). Anything else differing → stop and report.

- [ ] **Step 3: Record results**

Summarize both diffs (file list + one representative hunk) in the task report and clean up: `rm -rf /tmp/oneof-diff`.

---

### Task 7: Drift experiment — USER CHECKPOINT (stop-and-ask)

**Files:** none until the user decides

The grilled decision is **verify-then-decide**: observe what the regenerated `from_json` does with unknown/missing discriminator values, then the USER picks the policy. Do not proceed past Step 2 without an answer.

- [ ] **Step 1: Run the experiment against the rebuilt SDK**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run python - <<'EOF'
import sys
sys.path.insert(0, "/home/ubuntu/git/prisma-browser-sdk")
from prisma_browser.models.application_item import ApplicationItem

base = {
    "id": "app-1", "name": "x",
    "metadata": {"createdTime": "2026-01-01T00:00:00Z",
                 "lastUpdatedTime": "2026-01-01T00:00:00Z"},
    "urls": ["*.example.com"],
}
print("known   :", type(ApplicationItem.from_dict(
    {**base, "type": "catalog"}).actual_instance).__name__)
for label, payload in [
    ("unknown ", {**base, "type": "shiny-new-kind"}),
    ("missing ", dict(base)),
]:
    try:
        item = ApplicationItem.from_dict(payload)
        print(label, ": fell back ->", type(item.actual_instance).__name__)
    except Exception as exc:
        print(label, ": raised", type(exc).__name__, "—", str(exc)[:200])
EOF
```

- [ ] **Step 2: STOP — present to the user**

Report verbatim: the three outcomes, plus the emitted `from_json` source for the discriminator path (from Task 5 Step 2). The user chooses:

- **(a) Accept** the observed behavior → document it in the TODO entry from Task 3 (one sentence: "unknown discriminator values currently <observed behavior>") and finish the task with that docs commit.
- **(b) Patch for graceful drift** → unknown values must degrade to today's behavior (trial deserialization). This means a new regex patch in `src/phantasos/patches.py` rewriting the emitted raise/lookup-miss path to fall through to the trial loop, plus a unit test in `tests/test_framework.py` (mirroring `test_oneof_first_match_patch`) and a case added to `tests/test_sdk_oneof_real.py` asserting the fallback. The exact regex depends on the emitted shape recorded in Step 1 — write it at the checkpoint, with the user's confirmation, as an amendment task appended to this plan.

- [ ] **Step 3: Execute the chosen option and commit**

```bash
git add -A docs/ src/phantasos/patches.py tests/ 2>/dev/null
git commit -m "fix(oneof): drift policy per checkpoint decision"
```

(Adjust the message to match the actual decision: docs-only for (a), patch for (b).)

---

### Task 8: CLI rebuild + live re-verify + repair

**Files:**
- Regenerates: `/home/ubuntu/git/prisma-browser-cli` (sibling repo — do not commit it)
- Possibly modify: `products/prisma-browser/cli.yml` (only if a column path broke)

- [ ] **Step 1: Rebuild the CLI**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser
```

Expected: `emitted N files to /home/ubuntu/git/prisma-browser-cli (81 commands)` and zero unmapped-op warnings.

- [ ] **Step 2: Live verification (read-only calls; .env already present in the CLI repo)**

```bash
cd /home/ubuntu/git/prisma-browser-cli
uv sync
uv run prisma-browser show application --name google --output table
uv run prisma-browser show application --name google --output json | head -40
```

Check, in order:
1. Table renders with the curated columns (id, name, …) and no blank columns — the `actual_instance.*` JMESPath columns must still resolve now that `actual_instance` is a different class per row.
2. JSON output: catalog items now show `catalog_name`/`catalog_attributes` as TYPED top-level fields of the variant (not nested under `additional_properties`).
3. No `CustomApplicationAllOfType: value 'catalog' is not defined` warnings on stderr.

Then a single-item get (use a real id from the list output):

```bash
uv run prisma-browser show application --type catalog --id <ID-FROM-LIST>
```

Expected: clean single-object output typed as the catalog variant; the per-op `defaults:` runtime guard (sort/order dropped for the get binding) still works.

- [ ] **Step 3: Repair only what broke**

If a curated column renders empty or wrong, fix the JMESPath in `products/prisma-browser/cli.yml` `columns:` and re-run `phantasos cli build prisma-browser` + the Step 2 checks. Column *enhancements* (e.g. adding `catalog_name`) are roadmap, NOT this task. If the emitted runtime itself misbehaves, stop and report — that's a generator bug needing its own review, not a quiet fix.

- [ ] **Step 4: Commit (only if cli.yml changed)**

```bash
git add products/prisma-browser/cli.yml
git commit -m "fix(cli-config): repair application columns for typed oneOf variants"
```

---

### Task 9: Wrap-up — full gate + memory

- [ ] **Step 1: Full verification**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src
```

Expected: all pass / clean. Paste actual output in the report (evidence before assertions).

- [ ] **Step 2: Update project memory**

Append to the `prisma-browser-cli-generator-design` memory file: oneOf-discriminator-lookup shipped (date, HEAD sha, the `generator:` block migration, drift-policy decision from Task 7, sibling repos rebuilt-but-uncommitted).

- [ ] **Step 3: Handoff notes for the user**

Report: branch/HEAD, that `/home/ubuntu/git/prisma-browser-sdk` and `/home/ubuntu/git/prisma-browser-cli` are dirty with regenerated output awaiting their own commits, and the Task 7 drift decision.

---

## Self-review (done at planning time)

- **Spec coverage:** all 7 grill decisions map to tasks (scope→T2/T3, wiring+migration→T1, branch→process notes, drift→T7, CLI→T8, validation→T4/T5/T6, process→this plan).
- **Known unknowns made explicit:** emitted `from_json` shape with the flag (T5 records it), unknown-value behavior (T7 observes it), raw-spec OAG compatibility for adem (T6 has the preprocessed fallback).
- **Type consistency:** `GeneratorConfig.oneof_discriminator_lookup` ↔ `generate(oneof_discriminator_lookup=)` ↔ `cfg.generator.oneof_discriminator_lookup` — consistent throughout.
