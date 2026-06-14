# oneOf Wrapper Clean Output — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generated prisma-browser-cli emit clean payloads for oneOf endpoints (e.g. `show access-and-data-policy`) — no openapi-generator wrapper scaffolding (`actual_instance` / `one_of_schemas` / `oneof_schema_*_validator` / `discriminator_value_class_map`) and no empty `additional_properties: {}` — while keeping the existing snake_case output contract.

**Architecture:** Two generic SDK codegen patches (in `patches.py`) attach pydantic `model_serializer`s to the generated models so `model_dump()` behaves correctly for every consumer: a *plain* serializer on each oneOf wrapper returns its `actual_instance` (unwrap), and a *wrap* serializer on each model drops an empty `additional_properties` bag (non-empty bags are preserved). Because the CLI's output renderer already serializes via `model_dump(mode="json")`, no CLI render-path code changes. The CLI column subsystem is coupled to the old scaffolding (curated `actual_instance.*` columns + introspection that reported wrapper fields), so it is updated in lockstep: response-item introspection now reports the union (superset) of the variant models' fields, and `cli.yml`'s curated `application` columns drop the `actual_instance.` prefix.

**Tech Stack:** Python 3.12+, pydantic v2, openapi-generator (python), Typer/Rich (generated CLI), uv, nox, pytest, ruff, mypy.

---

## Background (validated findings — do not re-derive)

All of the following were reproduced against the live SDK before this plan was written:

- The SDK model is **not** wrong: `PolicyItem.to_dict()` already unwraps. The leak is that the CLI renderer calls pydantic `model_dump(mode="json")`, and openapi-generator puts unwrap logic only in the hand-written `to_dict()` — not in a pydantic serializer. So `model_dump` dumps the wrapper's literal fields.
- A plain `@model_serializer` returning `self.actual_instance`, placed **on the declared wrapper class**, makes a parent's `model_dump` unwrap nested wrappers (pydantic v2 serializes by declared type; a subclass serializer would be ignored). Verified: clean output, `by_alias`/`exclude_none`/`mode` propagate to the inner instance, zero pydantic warnings.
- A `@model_serializer(mode="wrap")` that pops an empty `additional_properties` composes correctly with the unwrap serializer (parent wrap → child unwrap → grandchild wrap), preserves non-empty bags, and propagates context. Verified, zero warnings.
- **Request path is safe:** the SDK serializes outbound bodies/params via `to_dict()` (`api_client.sanitize_for_serialization`), not `model_dump`. `to_dict()` internally calls `model_dump(by_alias=True, exclude={"additional_properties"}, exclude_none=True)`; the wrap serializer's handler respects `exclude=`, so `to_dict()` output is **byte-identical** before/after the patch (verified for empty and non-empty bags).
- **Flags/options are safe:** command flags, body flags, and `set <obj> <variant>` subcommands are generated from `model_fields`/type-hints at build time; a serializer changes neither.
- **Column coupling is real and forces the introspection change:** `resolve_columns` raises → build failure on an unknown root field. With the introspection change, the old `cli.yml` `application` columns (`actual_instance.id`) fail validation (`unknown field 'actual_instance'`), so `cli.yml` must be rewritten in the same change.
- **Cross-product reach is safe (verified):** `apply_generic_patches` runs for every product (default-on), so adem and scm models also get the serializers. adem has 20 oneOf wrappers but no `cli.yml` / no CLI surface consuming them (unwrap is cosmetic in raw JSON) and zero `additional_properties` fields (drop-empty is a no-op); only `products/prisma-browser/cli.yml` references `actual_instance.*`. `products/scm` has no `sdk.yml`/`cli.yml` and is unbuildable today, so the patches cannot reach it. No other product's columns break.

### Confirmed scope — five oneOf-list commands

Current (broken) vs target columns, confirmed by prototyping the introspection change:

| Command | Current columns | Target columns |
|---|---|---|
| `show:access-and-data-policy` | `['one_of_schemas']` | `['id','name','type','description','mode','evaluation_order']` |
| `show:sign-in-policy` | `['one_of_schemas']` | `['id','name','type','description','mode','evaluation_order']` |
| `show:security-policy` | `['one_of_schemas']` | `['id','name','type','description','mode','evaluation_order']` |
| `show:customization-policy` | `['one_of_schemas']` | `['id','name','type','description','mode','evaluation_order']` |
| `show:application` | `['actual_instance.id', …]` (curated) | `['id','name','type','description']` (curated, bare) |

### Files touched

- **Modify** `src/phantasos/generator/sdk/patches.py` — add two patch functions + an import helper; wire both into `apply_generic_patches`.
- **Modify** `src/phantasos/generator/cli/introspect.py` — add `_item_fields()`; use it in `_response_info()`.
- **Modify** `products/prisma-browser/cli.yml` — rewrite curated `application` columns to bare field names; update the explanatory comment.
- **Create** `tests/test_sdk_patches.py` — unit tests for the two patch functions (mechanics + idempotency + runtime behavior).
- **Modify** `tests/test_sdk_oneof_real.py` — add real-SDK regression tests for unwrap + drop-empty `additional_properties`.
- **Modify** `tests/test_cli_emitted_real.py` — update the `application` column assertion to bare names; assert a policy command now gets real default columns.
- **Modify** `CHANGELOG.md` — add a `## [Unreleased] → ### Fixed` entry.
- **Regenerated artifact (not committed):** `../prisma-browser-sdk` (sibling of the repo) is rebuilt so the patches are applied.

### Environment note (from CLAUDE.md)

This repo may sit on sshfs. Prefix uv with an explicit env dir and relocate nox venvs:
- `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run …`
- For `nox -s smoke`/`live`: also `NOX_ENVDIR=/tmp/phantasos-nox`.

---

## Task 1: Setup — branch, spec, and read the subsystem deep-dives

**Files:** none (git + reading only)

- [x] **Step 1: Feature branch + spec/plan are already in place**

`feature/oneof-wrapper-clean-output` is branched off the up-to-date `develop`; the
plan (`docs/plans/2026-06-14-oneof-wrapper-clean-output.md`) and the design spec
(`docs/specs/2026-06-14-oneof-wrapper-clean-output-design.md`) are committed on it.
Confirm with `git branch --show-current` → `feature/oneof-wrapper-clean-output`.

> Per CLAUDE.md: feature branches PR back into `develop` (squash-merge) and **must not** bump the version. Changes are recorded under `## [Unreleased]`.

- [ ] **Step 2: Read the subsystem deep-dives before touching code (required by CLAUDE.md)**

This change touches the SDK generator and the CLI generator. Read both deep-dives now:

Run: `sed -n '1,200p' .agents/context/sdk-generator.md && sed -n '1,200p' .agents/context/cli-generator.md`
Expected: you understand the SDK build pipeline (preprocess → generate → patch → vendor → smoke; where `patches.apply_generic_patches` runs) and the CLI introspect→classify→render pipeline (where `introspect._response_info` and column resolution live). These deep-dives are updated after implementation in Task 8.

---

## Task 2: SDK serializer patches (`patches.py`)

**Files:**
- Modify: `src/phantasos/generator/sdk/patches.py`
- Test: `tests/test_sdk_patches.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sdk_patches.py`:

```python
"""Unit tests for the oneOf-unwrap and drop-empty-additional_properties SDK patches."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from phantasos.generator.sdk import patches

_INNER_SRC = '''\
from __future__ import annotations
import pprint
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict


class Inner(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: str
    additional_properties: Dict[str, Any] = {}

    def to_str(self) -> str:
        return pprint.pformat(self.model_dump())
'''

_WRAPPER_SRC = '''\
from __future__ import annotations
import pprint
from pydantic import BaseModel, ConfigDict
from typing import Any, Optional, Set
from patch_fixture_inner import Inner


class Wrapper(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    actual_instance: Optional[Inner] = None
    one_of_schemas: Set[str] = {"Inner"}

    def to_str(self) -> str:
        return pprint.pformat(self.model_dump())
'''


def _write_fixture(models: Path) -> None:
    (models / "patch_fixture_inner.py").write_text(_INNER_SRC, encoding="utf-8")
    (models / "patch_fixture_wrapper.py").write_text(_WRAPPER_SRC, encoding="utf-8")


def test_patches_target_disjoint_files_and_are_idempotent(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    # drop-empty targets only the regular model; unwrap targets only the wrapper
    assert patches.patch_drop_empty_additional_properties(tmp_path) == 1
    assert patches.patch_oneof_unwrap_serializer(tmp_path) == 1
    # idempotent re-runs make no further changes
    assert patches.patch_drop_empty_additional_properties(tmp_path) == 0
    assert patches.patch_oneof_unwrap_serializer(tmp_path) == 0


def test_patched_models_serialize_cleanly(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    patches.patch_drop_empty_additional_properties(tmp_path)
    patches.patch_oneof_unwrap_serializer(tmp_path)

    sys.path.insert(0, str(tmp_path))
    try:
        for mod in ("patch_fixture_inner", "patch_fixture_wrapper"):
            sys.modules.pop(mod, None)
        Inner = importlib.import_module("patch_fixture_inner").Inner
        Wrapper = importlib.import_module("patch_fixture_wrapper").Wrapper

        # empty additional_properties is dropped
        assert Inner(id="x").model_dump(mode="json") == {"id": "x"}
        # non-empty additional_properties is preserved
        i2 = Inner(id="y")
        i2.additional_properties = {"k": 1}
        assert i2.model_dump(mode="json") == {"id": "y", "additional_properties": {"k": 1}}
        # oneOf wrapper unwraps to its actual_instance (and that inner drops empty bag)
        assert Wrapper(actual_instance=Inner(id="z")).model_dump(mode="json") == {"id": "z"}
    finally:
        sys.path.remove(str(tmp_path))
        for mod in ("patch_fixture_inner", "patch_fixture_wrapper"):
            sys.modules.pop(mod, None)


def test_apply_generic_patches_reports_new_counts(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    (pkg / "models").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    _write_fixture(pkg / "models")
    stats = patches.apply_generic_patches(pkg)
    assert stats["oneof_unwrap"] == 1
    assert stats["drop_empty_additional_properties"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_patches.py -v`
Expected: FAIL — `AttributeError: module 'phantasos.generator.sdk.patches' has no attribute 'patch_drop_empty_additional_properties'`.

- [ ] **Step 3: Implement the two patches + import helper**

In `src/phantasos/generator/sdk/patches.py`, update the module docstring bullet list (add two lines) and add the new code. First extend the docstring:

```python
"""Generic codegen-bug patches for OpenAPI Generator (python) output.

Spec-agnostic; applied to any generated package. Idempotent.
  - apostrophe enum values (`'Old McDonald's Farm'`) -> re-quoted
  - lenient enums (str+int) -> tolerate values newer than the spec
  - oneOf first-match -> from_json returns the first matching branch
  - oneOf unwrap -> model_dump serializes the wrapper as its actual_instance
  - drop empty additional_properties -> model_dump omits the empty bag
"""
```

Then add the following constants and functions (place them just above `def apply_generic_patches`):

```python
_UNWRAP_METHOD = '''
    @model_serializer
    def _phantasos_unwrap(self) -> Any:
        """phantasos: serialize a oneOf wrapper as its actual instance, so
        model_dump()/model_dump_json() match the hand-written to_dict() instead
        of leaking the generator scaffolding (actual_instance, one_of_schemas, ...)."""
        return self.actual_instance
'''

_DROP_EMPTY_METHOD = '''
    @model_serializer(mode="wrap")
    def _phantasos_drop_empty_additional_properties(self, handler) -> Any:
        """phantasos: omit an empty additional_properties bag from
        model_dump()/model_dump_json(); non-empty bags are left untouched.
        Respects exclude=/by_alias=/exclude_none=, so to_dict() is unchanged."""
        data = handler(self)
        if isinstance(data, dict) and data.get("additional_properties") == {}:
            data.pop("additional_properties")
        return data
'''


def _ensure_model_serializer_import(text: str) -> str:
    # Key on the IMPORT, not a bare `model_serializer` substring, so an unrelated
    # reference (a future field_serializer/model_validator, a hand-edit) can never
    # suppress a needed import while a method still gets injected (-> NameError).
    if "model_serializer," in text or "import model_serializer" in text:
        return text
    return text.replace(
        "from pydantic import ", "from pydantic import model_serializer, ", 1
    )


def patch_oneof_unwrap_serializer(models_dir: Path) -> int:
    """Attach a plain model_serializer to each oneOf wrapper so model_dump unwraps."""
    count = 0
    for path in sorted(models_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "actual_instance" not in text or "one_of_schemas" not in text:
            continue
        if "_phantasos_unwrap" in text:
            continue  # idempotent
        text = _ensure_model_serializer_import(text)
        text = text.replace(
            "\n    def to_str(self)", _UNWRAP_METHOD + "\n    def to_str(self)", 1
        )
        path.write_text(text, encoding="utf-8")
        count += 1
    return count


def patch_drop_empty_additional_properties(models_dir: Path) -> int:
    """Attach a wrap model_serializer dropping empty additional_properties bags.

    Skips oneOf wrappers (they carry no additional_properties field and get the
    unwrap serializer instead); a class may have at most one model_serializer.
    """
    count = 0
    for path in sorted(models_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "additional_properties: Dict[str, Any] = {}" not in text:
            continue
        if "one_of_schemas" in text:
            continue  # belongs to the unwrap patch
        if "_phantasos_drop_empty_additional_properties" in text:
            continue  # idempotent
        text = _ensure_model_serializer_import(text)
        text = text.replace(
            "\n    def to_str(self)", _DROP_EMPTY_METHOD + "\n    def to_str(self)", 1
        )
        path.write_text(text, encoding="utf-8")
        count += 1
    return count
```

Finally, extend `apply_generic_patches` to call both:

```python
def apply_generic_patches(pkg_dir: Path) -> dict[str, int]:
    models = pkg_dir / "models"
    return {
        "apostrophe": patch_apostrophe_enums(models),
        "lenient_enums": rebase_lenient_enums(pkg_dir),
        "oneof_first_match": patch_oneof_first_match(models),
        "oneof_unwrap": patch_oneof_unwrap_serializer(models),
        "drop_empty_additional_properties": patch_drop_empty_additional_properties(models),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_patches.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Lint + type-check the changed file**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run ruff check src/phantasos/generator/sdk/patches.py tests/test_sdk_patches.py && UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run mypy src/phantasos/generator/sdk/patches.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/sdk/patches.py tests/test_sdk_patches.py
git commit -m "fix(sdk): unwrap oneOf wrappers and drop empty additional_properties in model_dump"
```

---

## Task 3: Rebuild the SDK so the patches apply

**Files:** none (regenerates the sibling `../prisma-browser-sdk`)

- [ ] **Step 1: Rebuild the prisma-browser SDK**

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s smoke`
Expected: builds prisma-browser + adem SDKs end-to-end (auto-provisions a JRE on first run; needs network once). Finishes without error.

- [ ] **Step 2: Verify the serializers landed in the generated source**

Run: `grep -l "_phantasos_unwrap" ../prisma-browser-sdk/prisma_browser/models/*.py | wc -l`
Expected: `9` (the nine oneOf wrappers).

Run: `grep -l "_phantasos_drop_empty_additional_properties" ../prisma-browser-sdk/prisma_browser/models/*.py | head`
Expected: many model files listed (every model carrying an `additional_properties` bag).

- [ ] **Step 3: Verify clean output directly against the rebuilt SDK**

Run:
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run python -c "
import sys; sys.path.insert(0, '../prisma-browser-sdk')
from prisma_browser.models.get_sign_in_policy200_response import GetSignInPolicy200Response
raw = {'pageInfo': {'hasNextPage': False, 'totalCount': 1},
       'data': [{'type':'Rule','id':'0RL01KS55MYYE0ZFWENJT2R0QNFRX','position':1,'name':'R','description':'','mode':'active','evaluationOrder':1}],
       'metadata': {'configurationVersion': {'id':'0CV01KS4TBNE9YGG090J0E7C5PK2V','status':'draft','number':0}}}
d = GetSignInPolicy200Response.from_dict(raw).model_dump(mode='json')
item = d['data'][0]
assert 'actual_instance' not in item and 'one_of_schemas' not in item, item
assert 'additional_properties' not in item, item
assert 'additional_properties' not in d['page_info'], d['page_info']
print('OK clean:', item)
"
```
Expected: `OK clean: {'id': '0RL01KS55MYYE0ZFWENJT2R0QNFRX', 'position': 1, 'name': 'R', 'type': 'Rule', 'section': None, 'description': '', 'mode': 'active', 'evaluation_order': 1}`

No commit (regenerated artifact is not tracked).

---

## Task 4: Real-SDK regression tests for serializer behavior

**Files:**
- Modify: `tests/test_sdk_oneof_real.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sdk_oneof_real.py`:

```python
def test_oneof_model_dump_unwraps_and_drops_empty_additional_properties() -> None:
    """A oneOf list response serializes to clean rows: no wrapper scaffolding and
    no empty additional_properties bag (snake_case contract preserved)."""
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    sys.path.insert(0, str(REAL_SDK))
    try:
        try:
            from prisma_browser.models.get_sign_in_policy200_response import (
                GetSignInPolicy200Response,
            )
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        raw = {
            "pageInfo": {"hasNextPage": False, "totalCount": 1},
            "data": [
                {
                    "type": "Rule",
                    "id": "0RL01KS55MYYE0ZFWENJT2R0QNFRX",
                    "position": 1,
                    "name": "R",
                    "description": "",
                    "mode": "active",
                    "evaluationOrder": 1,
                }
            ],
            "metadata": {
                "configurationVersion": {
                    "id": "0CV01KS4TBNE9YGG090J0E7C5PK2V",
                    "status": "draft",
                    "number": 0,
                }
            },
        }
        dumped = GetSignInPolicy200Response.from_dict(raw).model_dump(mode="json")
    finally:
        sys.path.remove(str(REAL_SDK))

    item = dumped["data"][0]
    assert "actual_instance" not in item
    assert "one_of_schemas" not in item
    assert "oneof_schema_1_validator" not in item
    assert "additional_properties" not in item
    assert item["id"] == "0RL01KS55MYYE0ZFWENJT2R0QNFRX"
    assert item["type"] == "Rule"
    assert item["evaluation_order"] == 1  # snake_case contract
    assert "additional_properties" not in dumped["page_info"]


def test_non_empty_additional_properties_is_preserved() -> None:
    """A field the spec does not declare survives model_dump (lenient pass-through)."""
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    sys.path.insert(0, str(REAL_SDK))
    try:
        try:
            from prisma_browser.models.rule_summary import RuleSummary
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        rule = RuleSummary.from_dict(
            {
                "type": "Rule",
                "id": "0RL01KS55MYYE0ZFWENJT2R0QNFRX",
                "position": 1,
                "name": "R",
                "mode": "active",
                "evaluationOrder": 1,
                "surpriseField": 42,
            }
        )
        dumped = rule.model_dump(mode="json")
        as_dict = rule.to_dict()
    finally:
        sys.path.remove(str(REAL_SDK))

    assert dumped["additional_properties"] == {"surpriseField": 42}
    # to_dict() (the SDK request path) still hoists extras and uses aliases
    assert as_dict["surpriseField"] == 42
    assert as_dict["evaluationOrder"] == 1
    assert "additional_properties" not in as_dict
```

- [ ] **Step 2: Run the tests to verify they pass against the rebuilt SDK**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_sdk_oneof_real.py -v`
Expected: PASS (existing parametrized cases + the two new tests). If the SDK was not rebuilt in Task 3, they SKIP — rebuild first.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sdk_oneof_real.py
git commit -m "test(sdk): assert oneOf model_dump unwraps, drops empty bags, preserves extras"
```

---

## Task 5: Introspection — union (superset) of variant fields for oneOf list items

**Files:**
- Modify: `src/phantasos/generator/cli/introspect.py`
- Test: `tests/test_cli_emitted_real.py`

- [ ] **Step 1: Write the failing test (real-SDK column assertions)**

In `tests/test_cli_emitted_real.py`, replace the existing `application` column assertion block. Find:

```python
    # application columns: JMESPath paths through actual_instance union wrapper
    show_app = next(c for c in ir.commands if c.key == "show:application")
    assert [c.path for c in show_app.columns][:2] == [
        "actual_instance.id",
        "actual_instance.name",
    ]
    assert show_app.items_field == "data"
```

Replace with:

```python
    # application columns: bare variant fields (oneOf items report the union of
    # variant fields, so no actual_instance.* prefix is needed)
    show_app = next(c for c in ir.commands if c.key == "show:application")
    assert [c.path for c in show_app.columns] == ["id", "name", "type", "description"]
    assert show_app.items_field == "data"
    # a policy list (uncurated, oneOf RuleSummary|Section) gets real default columns
    show_adp = next(c for c in ir.commands if c.key == "show:access-and-data-policy")
    assert [c.path for c in show_adp.columns][:3] == ["id", "name", "type"]
    assert "one_of_schemas" not in [c.path for c in show_adp.columns]
    assert "actual_instance" not in {col.path.split(".")[0] for col in show_adp.columns}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_cli_emitted_real.py -k columns -v`
Expected: FAIL — current columns are `actual_instance.*` (application) and `['one_of_schemas']` (policy). (If it errors instead with a build `ValueError` about `actual_instance`, that means Task 6 ran first; do Task 5 implementation then Task 6.)

- [ ] **Step 3: Add the `_item_fields` helper**

In `src/phantasos/generator/cli/introspect.py`, add this function immediately after `_union_members` (and before `_response_info`):

```python
def _item_fields(item: type[BaseModel]) -> list[FieldInfo]:
    """Fields for a response list item.

    For a oneOf wrapper, return the union (superset) of every variant model's
    fields (dedup by name, first-seen order) instead of the wrapper scaffolding
    (actual_instance / one_of_schemas / ...). This lets default and curated
    columns resolve against the real variant fields.
    """
    members = _union_members(item)
    if not members:
        return _model_fields(item)
    ns: ModuleType = sys.modules[item.__module__]
    seen: set[str] = set()
    out: list[FieldInfo] = []
    for name in members:
        member_cls = getattr(ns, name, None)
        # Skip anything that isn't a real model: a member literally named "List"
        # would resolve to typing.List via getattr (not None), and _model_fields
        # would then crash. Not triggered by today's list-response wrappers, but
        # cheap insurance against a List/Dict-named variant becoming a list item.
        if not (isinstance(member_cls, type) and issubclass(member_cls, BaseModel)):
            continue
        for field in _model_fields(member_cls):
            if field.name in seen:
                continue
            seen.add(field.name)
            out.append(field)
    return out
```

- [ ] **Step 4: Use `_item_fields` in `_response_info`**

In the same file, in `_response_info`, change the two return statements. Find:

```python
        if isinstance(item, type) and issubclass(item, BaseModel):
            return base.__name__, fname, _model_fields(item)
    return base.__name__, None, _model_fields(base)
```

Replace with:

```python
        if isinstance(item, type) and issubclass(item, BaseModel):
            return base.__name__, fname, _item_fields(item)
    return base.__name__, None, _item_fields(base)
```

- [ ] **Step 5: Run the test — it still fails on `application` until cli.yml is rewritten**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_cli_emitted_real.py -k columns -v`
Expected: FAIL with a build `ValueError`: `cli.yml columns.application: unknown field 'actual_instance' in 'actual_instance.id'`. This is the expected forcing function — the introspection change makes the old curated columns invalid. Proceed to Task 6 to complete this red→green.

- [ ] **Step 6: Lint + type-check**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run ruff check src/phantasos/generator/cli/introspect.py && UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run mypy src/phantasos/generator/cli/introspect.py`
Expected: no errors.

> Commit happens in Task 6 (introspection + cli.yml are one logical, co-dependent change).

---

## Task 6: Rewrite curated `application` columns in `cli.yml`

**Files:**
- Modify: `products/prisma-browser/cli.yml`
- Test: `tests/test_cli_emitted_real.py` (the assertions added in Task 5)

- [ ] **Step 1: Rewrite the columns block + comment**

In `products/prisma-browser/cli.yml`, find:

```yaml
# NOTE: ApplicationItem is a OneOf union whose data field holds variant objects
# (CustomApplication, PrivateApplication, …) wrapped in actual_instance. The
# JMESPath root "actual_instance" IS a valid root field on ApplicationItem, so
# paths of the form actual_instance.<field> pass build validation and resolve at
# runtime for every variant that exposes the field.
columns:
  device-group:
    - id
    - name
    - platform
    - created_by
    - devices
    - created_at
  application:
    - {header: id,          path: actual_instance.id}
    - {header: name,        path: actual_instance.name}
    - {header: type,        path: actual_instance.type}
    - {header: description, path: actual_instance.description}
```

Replace with:

```yaml
# NOTE: ApplicationItem is a OneOf union (CustomApplication, PrivateApplication,
# …). Response-item introspection reports the union (superset) of the variant
# fields, so curated columns are bare field names — no actual_instance.* prefix.
# A field absent from a given variant simply renders empty for that row.
columns:
  device-group:
    - id
    - name
    - platform
    - created_by
    - devices
    - created_at
  application:
    - id
    - name
    - type
    - description
```

- [ ] **Step 2: Run the columns test — now green**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run pytest tests/test_cli_emitted_real.py -k columns -v`
Expected: PASS — `application` → `['id','name','type','description']`; `show:access-and-data-policy` first three columns `['id','name','type']`, no `one_of_schemas`.

- [ ] **Step 3: Commit introspection + cli.yml together**

```bash
git add src/phantasos/generator/cli/introspect.py products/prisma-browser/cli.yml tests/test_cli_emitted_real.py
git commit -m "fix(cli): report oneOf variant union as response item fields; debare application columns"
```

---

## Task 7: Sweep for any other tests asserting the old shape

**Files:**
- Modify: any test files surfaced by the sweep (expected: none beyond Tasks 4–6)

- [ ] **Step 1: Search for stale assertions**

Run:
```bash
grep -rn "actual_instance\|one_of_schemas\|oneof_schema_1_validator\|discriminator_value_class_map" tests/ | grep -v "test_sdk_patches.py" | grep -v "test_sdk_oneof_real.py" | grep -v "test_framework.py"
```
Expected: only legitimate references remain (e.g. `test_cli_emitted_real.py` accessing `body.actual_instance` on an in-memory request wrapper at lines ~188/229, and the `_union_members` helper detection). In-memory `.actual_instance` attribute access is unaffected by the serializer — leave those. If any test asserts the *serialized* presence of scaffolding, update it to assert the cleaned shape.

- [ ] **Step 2: Search for additional_properties output assertions**

Run: `grep -rn "additional_properties" tests/`
Expected: review each. Any test asserting `additional_properties: {}` appears in *serialized CLI/model_dump output* must flip to asserting its absence. Tests using `additional_properties` as an in-memory attribute (e.g. `test_catalog_fields_are_typed_not_demoted`) are unaffected — leave them.

- [ ] **Step 3: Commit (only if changes were needed)**

```bash
git add -A tests/
git commit -m "test: align remaining assertions with cleaned oneOf/additional_properties output"
```

If the sweep found nothing to change, skip this commit.

---

## Task 8: Update the agent-context deep-dives + refresh generated blocks

**Files:**
- Modify: `.agents/context/sdk-generator.md`
- Modify: `.agents/context/cli-generator.md`

Required by the CLAUDE.md `.agents/context/` working agreement: after a change that alters a subsystem, update its deep-dive's narrative and refresh its generated blocks.

- [ ] **Step 1: Update `sdk-generator.md` narrative**

In `.agents/context/sdk-generator.md`, in the section describing the generic patches (search for `apply_generic_patches` / `patch_oneof_first_match`), add a sentence covering the two new patches: the oneOf **unwrap** serializer (model_dump serializes a wrapper as its `actual_instance`) and the **drop-empty-`additional_properties`** wrap serializer (model_dump omits an empty bag; non-empty preserved; `to_dict()`/request path unchanged because the wrap handler respects `exclude=`).

- [ ] **Step 2: Update `cli-generator.md` narrative**

In `.agents/context/cli-generator.md`, in the introspection/column section (search for `_response_info` / columns), note that oneOf list items now report the **union (superset)** of variant fields (`_item_fields`), so default/curated columns resolve against real variant fields (no `actual_instance.` prefix).

- [ ] **Step 3: Refresh generated blocks and verify**

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s context`
Then verify the check passes: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s context -- --check`
Expected: generated blocks refreshed; `--check` exits 0 (clean).

- [ ] **Step 4: Commit**

```bash
git add .agents/context/sdk-generator.md .agents/context/cli-generator.md
git commit -m "docs(context): note oneOf unwrap/drop-empty serializers and union item-fields"
```

---

## Task 9: Full offline gate + live gate + manual evidence

**Files:** none

- [ ] **Step 1: Offline gate (ruff + mypy + pytest)**

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s gate`
Expected: PASS — ruff clean, mypy clean, full pytest suite green.

- [ ] **Step 2: Live gate (real tenant CRUD)**

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s live`
Expected: rebuilds the SDK and runs the live CRUD suite. With `CLIENT_ID`/`CLIENT_SECRET`/`SCOPE` present (via `.env`), it exercises real CRUD; without them it SKIPS (still green). Capture the output as evidence.

- [ ] **Step 3: Manual end-to-end evidence (requires credentials)**

Run the emitted CLI against the real tenant and confirm the clean payload:
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run prisma-browser-cli show access-and-data-policy
```
Expected: `data[]` items are flat objects (`id`, `position`, `name`, `type`, `description`, `mode`, `evaluation_order`) — no `actual_instance` / `one_of_schemas` / `oneof_schema_*_validator` / `discriminator_value_class_map`, and no empty `additional_properties: {}`.

Also confirm the table view:
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run prisma-browser-cli show access-and-data-policy -o table
```
Expected: columns `id  name  type  description  mode  evaluation_order` with populated rows (not blank).

> Per the test policy: paste the real command output before claiming success.

---

## Task 10: Changelog + PR

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add the Unreleased → Fixed entry**

In `CHANGELOG.md`, under `## [Unreleased]` → `### Fixed`, add as the first bullet:

```markdown
- Generated CLIs now render clean payloads for oneOf endpoints (e.g. `show access-and-data-policy`): the openapi-generator wrapper scaffolding (`actual_instance`, `one_of_schemas`, `oneof_schema_*_validator`, `discriminator_value_class_map`) no longer leaks into `--output json/yaml`, and empty `additional_properties: {}` bags are omitted (non-empty bags — fields the spec hasn't caught up to — are preserved). Two generic SDK serializer patches drive this, so every `model_dump()` consumer benefits; the outbound request path (which uses `to_dict()`) is unchanged. Curated/default table columns for oneOf list commands now resolve against the real variant fields (e.g. `application`, `access-and-data-policy`) instead of showing the wrapper.
```

- [ ] **Step 2: Verify the changelog edit and run the offline gate once more**

Run: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s gate`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note clean oneOf output + additional_properties cleanup"
```

- [ ] **Step 4: Push and open the PR against `develop`**

```bash
git push "https://x-access-token:$(gh auth token)@github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner).git" feature/oneof-wrapper-clean-output
gh pr create --base develop --title "Clean oneOf output for generated CLIs" \
  --body "Removes openapi-generator oneOf wrapper scaffolding and empty additional_properties from generated-CLI output via two generic SDK model_serializer patches, and reworks the coupled column subsystem (union-superset item fields + debared application columns). Request path (to_dict) byte-identical; flags/options unaffected. See docs/plans/2026-06-14-oneof-wrapper-clean-output.md."
```

Expected: PR opened against `develop` (squash-merge; **no version bump**).

---

## Self-Review

**Spec coverage:**
- oneOf scaffolding removal → Task 2 (unwrap serializer) + Task 3 (rebuild) + Task 4 (regression).
- Empty `additional_properties` cleanup, drop-empty-only, non-empty preserved → Task 2 (wrap serializer) + Task 4 (preservation test).
- Snake_case contract kept → asserted in Task 4 (`evaluation_order`).
- Request path unaffected → Task 4 (`to_dict()` assertions).
- Column coupling (mandatory) → Task 5 (introspection) + Task 6 (cli.yml), with the build-failure forcing function exercised in Task 5 Step 5.
- All five affected commands → Task 6 verification (application + access-and-data-policy; the other three policies share the same code path and default-column logic).
- Stale test sweep → Task 7.
- Agent-context deep-dives updated + `nox -s context` refreshed → Task 8 (per the `.agents/context/` working agreement).
- Acceptance bar (offline regression + live gate + manual) → Task 9; CHANGELOG → Task 10.

**Placeholder scan:** none — every code/edit step contains the literal content and exact anchors.

**Type/name consistency:** `patch_oneof_unwrap_serializer`, `patch_drop_empty_additional_properties`, `_ensure_model_serializer_import`, `_item_fields` are used consistently across Tasks 2/5/`apply_generic_patches`. Serializer method names (`_phantasos_unwrap`, `_phantasos_drop_empty_additional_properties`) match between the patch source and the idempotency guards. `model_serializer` import is ensured before use in both patches.
