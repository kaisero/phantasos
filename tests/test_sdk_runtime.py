"""Offline unit test for the libcst runtime-hoist pass (P1.2).

The fixture is seeded from the REAL OAG shapes captured from the first-light
``prisma-access-sdk`` build — the multi-line ``def __init__(...) -> None:`` (B1),
the non-dotted ``from prisma_access.<slug> import rest`` (B2), the relative
``from ..exceptions import`` in ``extras/errors.py`` (B3), the multi-line
``from prisma_access.<slug>.exceptions import (...)`` block, the ``T as
ApiResponseT`` alias, ``import prisma_access.<slug>.models`` + ``getattr(
prisma_access.<slug>.models, klass)`` — so the test fails-before for the genuine
defects, not just the happy path. It also encodes the real-tree gap the brief's
api+extras-only walk would miss: ``<slug>/__init__.py`` re-exports the runtime
symbols (``from prisma_access.<slug>.api_client import ApiClient as ApiClient``),
and importing anything under ``<slug>`` executes that ``__init__.py``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from phantasos.generator.sdk.runtime import hoist_runtime

_RT_NAMES = ("api_client", "configuration", "rest", "exceptions", "api_response")


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _api_client_src(slug: str) -> str:
    # Mirrors prisma_access/objects/api_client.py: import block (lines 30-42),
    # multi-line `def __init__(...) -> None:` and the package-bound
    # `getattr(prisma_access.<slug>.models, klass)` in __deserialize.
    return (
        '"""ApiClient (real-shape fixture)."""\n'
        f"from prisma_access.{slug}.configuration import Configuration\n"
        f"from prisma_access.{slug}.api_response "
        "import ApiResponse, T as ApiResponseT\n"
        f"import prisma_access.{slug}.models\n"
        f"from prisma_access.{slug} import rest\n"
        f"from prisma_access.{slug}.exceptions import (\n"
        "    ApiValueError,\n"
        "    ApiException,\n"
        ")\n"
        "\n"
        "RequestSerialized = tuple\n"
        "\n"
        "class ApiClient:\n"
        '    """Generic API client for OpenAPI client library builds."""\n'
        "    _pool = None\n"
        "    def __init__(\n"
        "        self,\n"
        "        configuration=None,\n"
        "        header_name=None,\n"
        "        header_value=None,\n"
        "        cookie=None\n"
        "    ) -> None:\n"
        "        if configuration is None:\n"
        "            configuration = Configuration.get_default()\n"
        "        self.configuration = configuration\n"
        "        self.rest_client = rest.RESTClientObject(configuration)\n"
        "    def _ApiClient__deserialize(self, data, klass):\n"
        "        if isinstance(klass, str):\n"
        f"            klass = getattr(prisma_access.{slug}.models, klass)\n"
        "        return klass\n"
    )


def _seed_subpackage(root: Path, slug: str) -> None:
    b = root / slug
    # <slug>/__init__.py re-exports runtime symbols (REAL shape, objects/__init__.py
    # lines 349-357) — the gap an api+extras-only walk would leave dangling.
    _write(
        b / "__init__.py",
        f"from prisma_access.{slug}.api_client import ApiClient as ApiClient\n"
        f"from prisma_access.{slug}.exceptions import ApiException as ApiException\n",
    )
    _write(b / "api_client.py", _api_client_src(slug))
    _write(
        b / "configuration.py",
        "class Configuration:\n    @classmethod\n    def get_default(cls):\n        return cls()\n",
    )
    _write(
        b / "api_response.py",
        "from typing import TypeVar\n\nT = TypeVar('T')\n\nclass ApiResponse:\n    pass\n",
    )
    _write(
        b / "exceptions.py",
        "class ApiException(Exception):\n    pass\nclass ApiValueError(ApiException):\n    pass\n",
    )
    _write(
        b / "rest.py",
        f"from prisma_access.{slug}.exceptions import ApiException, ApiValueError\n"
        "RESTResponseType = object\n"
        "class RESTClientObject:\n    def __init__(self, c):\n        pass\n",
    )
    _write(b / "api" / "__init__.py", "")
    _write(
        b / "api" / "thing_api.py",
        f"from prisma_access.{slug}.api_client import ApiClient, RequestSerialized\n"
        f"from prisma_access.{slug}.api_response import ApiResponse\n"
        f"from prisma_access.{slug}.rest import RESTResponseType\n"
        f"from prisma_access.{slug}.models.thing import Thing\n"
        # P1.2 collision: a SCHEMA named `Configuration` lands at
        # models/configuration.py — its import tail is runtime-named but it is NOT a
        # runtime module; the hoist must leave it pointing at the sub-package's models.
        f"from prisma_access.{slug}.models.configuration import Configuration\n",
    )
    _write(b / "extras" / "__init__.py", "")
    # B3: relative `from ..exceptions import` (extras module → runtime).
    _write(b / "extras" / "errors.py", "from ..exceptions import ApiException\n")
    _write(b / "models" / "__init__.py", "")
    _write(b / "models" / "thing.py", "class Thing:\n    pass\n")
    _write(b / "models" / "configuration.py", "class Configuration:\n    pass\n")


def test_hoist_runtime(tmp_path: Path) -> None:
    root = tmp_path / "prisma_access"
    _write(root / "__init__.py", "")
    for slug in ("objects", "posture"):
        _seed_subpackage(root, slug)

    hoist_runtime(tmp_path, "prisma_access", ["objects", "posture"])

    rt = root / "_runtime"
    for fname in _RT_NAMES:
        assert (rt / f"{fname}.py").exists(), f"_runtime/{fname}.py missing"

    ac = (rt / "api_client.py").read_text(encoding="utf-8")
    assert "models: object = None" in ac  # B1: class-level default (typed for the composer's assignment)
    assert "def __init__(" in ac and "-> None:" in ac  # B1: __init__ untouched
    assert "header_value=None" in ac  # B1: full multi-line signature intact
    assert "getattr(self.models, klass)" in ac
    # donor models-import dropped:
    assert "import prisma_access.objects.models" not in ac
    assert "from prisma_access._runtime import rest" in ac  # B2: non-dotted
    assert "from prisma_access._runtime.configuration import Configuration" in ac
    # alias preserved through the dotted-module rewrite:
    assert "from prisma_access._runtime.api_response import ApiResponse, T as ApiResponseT" in ac
    assert "from prisma_access._runtime.exceptions import" in ac  # multi-line block

    # _runtime/rest.py repointed to the shared exceptions:
    rest = (rt / "rest.py").read_text(encoding="utf-8")
    assert "from prisma_access._runtime.exceptions import" in rest

    # per-sub runtime files deleted:
    for slug in ("objects", "posture"):
        for fname in _RT_NAMES:
            assert not (root / slug / f"{fname}.py").exists()

    api = (root / "objects" / "api" / "thing_api.py").read_text(encoding="utf-8")
    # repointed AND the two-name import (ApiClient, RequestSerialized) preserved:
    assert "_runtime.api_client import ApiClient, RequestSerialized" in api
    assert "from prisma_access._runtime.api_response import ApiResponse" in api
    assert "from prisma_access._runtime.rest import RESTResponseType" in api
    # model import preserved (left untouched):
    assert "from prisma_access.objects.models.thing import Thing" in api
    # P1.2 collision-hardening: a model named like a runtime module (`Configuration`
    # → models/configuration.py) is a NON-direct child of the sub-package, so the
    # hoist must NOT rewrite it to `_runtime.configuration` (that would ImportError).
    assert "from prisma_access.objects.models.configuration import Configuration" in api
    assert "_runtime.configuration import Configuration" not in api

    err = (root / "objects" / "extras" / "errors.py").read_text(encoding="utf-8")
    assert "from prisma_access._runtime.exceptions import ApiException" in err  # B3

    # the slug __init__.py re-exports repointed at _runtime (the real-tree gap);
    # the `as X` alias tail is elided here only to keep the line short — alias
    # preservation through the rewrite is asserted on the api_response line above.
    init = (root / "objects" / "__init__.py").read_text(encoding="utf-8")
    assert "from prisma_access._runtime.api_client import ApiClient" in init
    assert "from prisma_access._runtime.exceptions import ApiException" in init

    # …and the whole hoisted tree imports cleanly (executes <slug>/__init__.py).
    # Isolate from any real `prisma_access` an earlier build test left in
    # sys.modules (its introspect step imports the real SDK, whose extras/ has no
    # errors.py) — else these submodules resolve against the wrong package. Save +
    # remove the pre-existing modules before importing tmp_path's; restore after.
    def _drop() -> dict[str, ModuleType]:
        return {
            m: sys.modules.pop(m) for m in list(sys.modules) if m == "prisma_access" or m.startswith("prisma_access.")
        }

    saved = _drop()
    sys.path.insert(0, str(tmp_path))
    try:
        importlib.invalidate_caches()
        importlib.import_module("prisma_access._runtime.api_client")
        importlib.import_module("prisma_access.objects.extras.errors")
        importlib.import_module("prisma_access.objects.api.thing_api")
    finally:
        sys.path.remove(str(tmp_path))
        _drop()
        sys.modules.update(saved)
