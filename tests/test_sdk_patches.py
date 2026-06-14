"""Unit tests for the oneOf-unwrap and drop-empty-additional_properties SDK patches."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from phantasos.generator.sdk import patches

_INNER_SRC = """\
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
"""

_WRAPPER_SRC = """\
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
"""


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
        Inner = importlib.import_module("patch_fixture_inner").Inner  # noqa: N806
        Wrapper = importlib.import_module("patch_fixture_wrapper").Wrapper  # noqa: N806

        # empty additional_properties is dropped
        assert Inner(id="x").model_dump(mode="json") == {"id": "x"}
        # non-empty additional_properties is preserved
        i2 = Inner(id="y")
        i2.additional_properties = {"k": 1}
        assert i2.model_dump(mode="json") == {
            "id": "y",
            "additional_properties": {"k": 1},
        }
        # oneOf wrapper unwraps to its actual_instance (and that inner drops empty bag)
        assert Wrapper(actual_instance=Inner(id="z")).model_dump(mode="json") == {
            "id": "z"
        }
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
