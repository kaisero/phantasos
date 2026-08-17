"""Unit tests for the oneOf-unwrap and drop-empty-additional_properties SDK patches.

Also covers the client-side scope mutual-exclusion validator
(``patch_scope_validators``).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

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


def test_patches_skip_when_to_str_anchor_absent(tmp_path: Path) -> None:
    """A marker-matching model without the `to_str` anchor is skipped, not counted
    and written back unchanged (guards against a silent no-op if OAG changes)."""
    wrapper_no_anchor = (
        "from pydantic import BaseModel\n"
        "from typing import Any, Optional, Set\n\n\n"
        "class Wrapper(BaseModel):\n"
        "    actual_instance: Optional[Any] = None\n"
        '    one_of_schemas: Set[str] = {"Inner"}\n'
    )
    inner_no_anchor = (
        "from pydantic import BaseModel\n"
        "from typing import Any, Dict\n\n\n"
        "class Inner(BaseModel):\n"
        "    id: str\n"
        "    additional_properties: Dict[str, Any] = {}\n"
    )
    (tmp_path / "wrapper_no_anchor.py").write_text(wrapper_no_anchor, encoding="utf-8")
    (tmp_path / "inner_no_anchor.py").write_text(inner_no_anchor, encoding="utf-8")
    assert patches.patch_oneof_unwrap_serializer(tmp_path) == 0
    assert patches.patch_drop_empty_additional_properties(tmp_path) == 0
    # files left byte-for-byte unchanged
    assert (tmp_path / "wrapper_no_anchor.py").read_text(encoding="utf-8") == wrapper_no_anchor
    assert (tmp_path / "inner_no_anchor.py").read_text(encoding="utf-8") == inner_no_anchor


def test_oneof_missing_imports_adds_only_existing_siblings(tmp_path: Path) -> None:
    """A oneOf wrapper that names a branch model in its `_OF_SCHEMAS` list but lacks
    the import (OAG's primitive-titled-branch defect, e.g. `Number`) gets it added —
    but only when the sibling module exists, and idempotently."""
    (tmp_path / "number.py").write_text(
        "from pydantic import BaseModel\n\n\nclass Number(BaseModel):\n    pass\n",
        encoding="utf-8",
    )
    wrapper = (
        "from __future__ import annotations\n"
        "from pydantic import BaseModel\n"
        "from typing import Optional, Union\n"
        "from pkg.models.tcp import Tcp\n\n"
        'PROTO_ONE_OF_SCHEMAS = ["Number", "Tcp", "Ghost"]\n\n\n'
        "class Proto(BaseModel):\n"
        "    actual_instance: Optional[Union[Number, Tcp]] = None\n"
    )
    (tmp_path / "proto.py").write_text(wrapper, encoding="utf-8")

    assert patches.patch_oneof_missing_imports(tmp_path, package="pkg") == 1
    text = (tmp_path / "proto.py").read_text(encoding="utf-8")
    assert "from pkg.models.number import Number\n" in text  # existing sibling added
    assert "import Ghost" not in text  # no module file -> not invented
    assert "import Tcp" in text  # the one OAG did emit is untouched
    # idempotent
    assert patches.patch_oneof_missing_imports(tmp_path, package="pkg") == 0


# --------------------------------------------------------------------------- #
# scope mutual-exclusion validator (patch_scope_validators)
# --------------------------------------------------------------------------- #

_SCOPED_MODEL_SRC = (
    "from pydantic import BaseModel\n\n"
    "class Addresses(BaseModel):\n"
    "    id: str | None = None\n"
    "    name: str | None = None\n"
    "    folder: str | None = None\n"
    "    snippet: str | None = None\n"
    "    device: str | None = None\n"
)


def _write_scoped(models: Path) -> None:
    models.mkdir(exist_ok=True)
    (models / "addresses.py").write_text(_SCOPED_MODEL_SRC, encoding="utf-8")


def test_scope_validator_injected_into_named_models(tmp_path: Path) -> None:
    models = tmp_path / "models"
    _write_scoped(models)
    n = patches.patch_scope_validators(models, ("folder", "snippet", "device"), {"addresses"})
    assert n == 1
    text = (models / "addresses.py").read_text(encoding="utf-8")
    assert "_phantasos_scope_exactly_one" in text
    assert "model_validator" in text  # import ensured
    # idempotent
    assert patches.patch_scope_validators(models, ("folder", "snippet", "device"), {"addresses"}) == 0


def test_scope_validator_skips_non_named_models(tmp_path: Path) -> None:
    """A model whose stem is not in the scoped set gets no validator."""
    models = tmp_path / "models"
    _write_scoped(models)
    other = (
        "from pydantic import BaseModel\n\n"
        "class Other(BaseModel):\n"
        "    id: str | None = None\n"
        "    folder: str | None = None\n"
    )
    (models / "other.py").write_text(other, encoding="utf-8")
    n = patches.patch_scope_validators(models, ("folder", "snippet", "device"), {"addresses"})
    assert n == 1  # only addresses
    assert "_phantasos_scope_exactly_one" not in (models / "other.py").read_text(encoding="utf-8")


def test_scope_validator_no_op_when_no_scoped_stems(tmp_path: Path) -> None:
    """A non-scoped product (empty stem set) gets no validator and no writes."""
    models = tmp_path / "models"
    _write_scoped(models)
    before = (models / "addresses.py").read_text(encoding="utf-8")
    assert patches.patch_scope_validators(models, ("folder", "snippet", "device"), set()) == 0
    assert (models / "addresses.py").read_text(encoding="utf-8") == before


def _load_scoped_model(tmp_path: Path) -> Any:
    models = tmp_path / "models"
    _write_scoped(models)
    patches.patch_scope_validators(models, ("folder", "snippet", "device"), {"addresses"})
    sys.path.insert(0, str(models))
    try:
        sys.modules.pop("addresses", None)
        return importlib.import_module("addresses").Addresses
    finally:
        sys.path.remove(str(models))


def test_scope_validator_runtime_behavior(tmp_path: Path) -> None:
    Addresses = _load_scoped_model(tmp_path)  # noqa: N806
    try:
        # exactly one container -> ok
        assert Addresses(name="a", folder="Shared").folder == "Shared"
        # zero containers on a user body -> raises (the one server-impossible shape)
        with pytest.raises(ValidationError):
            Addresses(name="a")
        # two containers, NO id -> tolerated: folder listings surface inherited
        # objects (e.g. SCM's `predefined` snippet) with several containers and
        # no id, so raising here would break reads. The server rejects a genuine
        # multi-container write itself.
        inherited = Addresses(name="a", folder="Shared", snippet="s")
        assert inherited.folder == "Shared" and inherited.snippet == "s"
        # server echo (id set) with zero containers -> NOT rejected
        echo0 = Addresses(id="uuid-1", name="a")
        assert echo0.id == "uuid-1"
        # server echo (id set) with two containers -> NOT rejected
        echo2 = Addresses(id="uuid-2", name="a", folder="Shared", snippet="s")
        assert echo2.id == "uuid-2"
        # model_validate of an echoed dict round-trips
        assert Addresses.model_validate({"id": "uuid-3", "name": "a"}).id == "uuid-3"
        # model_validate of an id-LESS inherited listing item round-trips
        pre = Addresses.model_validate({"name": "a", "folder": "Shared", "snippet": "predefined"})
        assert pre.snippet == "predefined"
    finally:
        sys.modules.pop("addresses", None)


def test_patch_missing_typing_imports_adds_used_but_unimported(tmp_path: Path) -> None:
    """OAG emits `List[...]`/`ClassVar[List[str]]` under future annotations while
    importing only a subset of typing (here: no `List`). The patch injects the
    missing name into the existing import line; runtime was fine but ruff F821 /
    mypy name-defined were not. Idempotent; touches only files missing the name."""
    (tmp_path / "widget.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Any, ClassVar, Optional\n\n\n"
        "class Widget:\n"
        "    __properties: ClassVar[List[str]] = ['a']\n"
        "    tags: Optional[List[str]] = None\n",
        encoding="utf-8",
    )
    # a file that already imports everything it uses is left alone
    (tmp_path / "ok.py").write_text(
        "from __future__ import annotations\nfrom typing import List\n\nx: List[int] = []\n",
        encoding="utf-8",
    )

    assert patches.patch_missing_typing_imports(tmp_path) == 1
    text = (tmp_path / "widget.py").read_text(encoding="utf-8")
    assert "from typing import Any, ClassVar, List, Optional\n" in text
    # idempotent, and the already-correct file is untouched
    assert patches.patch_missing_typing_imports(tmp_path) == 0
