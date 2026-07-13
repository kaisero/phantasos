"""Unit tests for the vendored idempotent-sync runtime templates."""

import enum
import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

from phantasos.generator.sdk import render


@pytest.fixture(autouse=True)
def _clean_idem_modules() -> Iterator[None]:
    """Drop stub `_ip*` modules between tests so render-and-exec stays hermetic."""
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name == "_ip" or name.startswith("_ip."):
            sys.modules.pop(name, None)


def _exec_idem_module(
    name: str, src: str, deps: dict[str, types.ModuleType]
) -> types.ModuleType:
    """Exec a rendered extras/idempotency/*.py in a stub package tree."""
    pkg = types.ModuleType("_ip")
    pkg.__path__ = []
    idem = types.ModuleType("_ip.extras.idempotency")
    idem.__path__ = []
    exc = types.ModuleType("_ip.exceptions")
    exc.NotFoundException = type("NotFoundException", (Exception,), {})  # type: ignore[attr-defined]
    mods = {
        "_ip": pkg,
        "_ip.extras": types.ModuleType("_ip.extras"),
        "_ip.extras.idempotency": idem,
        "_ip.exceptions": exc,
        **deps,
    }
    mods["_ip.extras"].__path__ = []
    sys.modules.update(mods)
    fqname = f"_ip.extras.idempotency.{name}"
    mod = types.ModuleType(fqname)
    mod.__package__ = "_ip.extras.idempotency"
    # Register BEFORE exec: `@dataclass` under `from __future__ import annotations`
    # resolves string annotations via `sys.modules[cls.__module__]`.
    sys.modules[fqname] = mod
    try:
        exec(compile(src, f"{name}.py", "exec"), mod.__dict__)  # noqa: S102
        return mod
    finally:
        pass  # left registered for dependent execs; cleaned per-test by autouse fixture


def _render_idem(template: str, **params: object) -> str:
    return render._env().get_template(f"idempotency/{template}").render(**params)


def test_base_exposes_registries_and_protocols() -> None:
    mod = _exec_idem_module("base", _render_idem("base.py.jinja", federated=False), {})
    assert mod.FETCH == {} and mod.MUTATE == {} and mod.MATERIALIZE == {}
    for proto in ("FetchStrategy", "MutateStrategy", "MaterializeStrategy"):
        assert hasattr(mod, proto)
    assert issubclass(mod.NotFoundException, Exception)


# --- SyncMixin orchestrator (engine.py.jinja) --------------------------------


def _engine_env() -> tuple[types.ModuleType, types.ModuleType]:
    """Render base + engine into one stub module namespace; return (base, engine)."""
    base_src = _render_idem("base.py.jinja", federated=False)
    base = _exec_idem_module("base", base_src, {})
    eng_src = _render_idem("engine.py.jinja", federated=False)
    eng = _exec_idem_module("engine", eng_src, {"_ip.extras.idempotency.base": base})
    return base, eng


class _Model:
    """Minimal pydantic-like stand-in with model_dump/to_dict."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)
        self._set = set(kw)

    def model_dump(
        self, *, by_alias: bool = True, mode: str = "json", exclude_unset: bool = False
    ) -> dict[str, object]:
        return {
            k: v
            for k, v in self.__dict__.items()
            if k not in ("_set",) and (not exclude_unset or k in self._set)
        }

    def to_dict(self) -> dict[str, object]:
        return self.model_dump()

    @classmethod
    def model_validate(cls, d: dict[str, object]) -> "_Model":
        return cls(**d)


def _meta(**over: object) -> dict[str, object]:
    m: dict[str, object] = {
        "identity": ["name"],
        "scope": None,
        "models": {"create": _Model, "update": _Model, "read": _Model},
        "input_fields": ["name", "description", "ip_netmask"],
        "server_only": ["id"],
        "id_field": {"wire": "id", "attr": "id"},
        "order_sensitive": [],
        "write_only": [],
        "projections": {},
        "singleton": False,
        "update": {"verb": "replace"},
        "fetch": "F",
        "mutate": "M",
        "materialize": "T",
        "fetch_opts": {"page_limit": 200, "hydrate": False},
    }
    m.update(over)
    return m


def _stub(
    base: types.ModuleType,
    eng: types.ModuleType,
    meta: dict[str, object],
    existing: object = None,
    record: list[Any] | None = None,
) -> tuple[Any, list[Any]]:
    rec: list[Any] = record if record is not None else []
    base.FETCH["F"] = lambda res, i, s, m: existing

    def _mutate(res: object, d: object, a: _Model, df: object, m: object) -> _Model:
        rec.append(("mutate", df))
        dump = {k: v for k, v in a.model_dump().items() if k != "id"}
        return _Model(id="x", **dump)

    base.MUTATE["M"] = _mutate
    base.MATERIALIZE["T"] = lambda res, resp, i, s, m: resp

    class Stub(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = meta

        def create(self, *, body: _Model) -> _Model:
            rec.append(("create", body))
            return _Model(id="new", **body.model_dump())

        def delete(self, *, id: object) -> None:
            rec.append(("delete", id))

    return Stub(), rec


def test_create_builds_body_and_calls_materialize() -> None:
    base, eng = _engine_env()
    res, rec = _stub(base, eng, _meta(), existing=None)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32"))
    assert r.changed and r.action == "created"
    assert any(k == "create" for k, _ in rec)


def test_reapply_identical_is_unchanged() -> None:
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, _ = _stub(base, eng, _meta(), existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32"))
    assert not r.changed and r.action == "unchanged"


def test_drift_calls_mutate_then_materialize() -> None:
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, rec = _stub(base, eng, _meta(), existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="2.2.2.2/32"))
    assert r.changed and r.action == "updated"
    assert set(r.diff.changes) == {"ip_netmask"}
    assert any(k == "mutate" for k, _ in rec)


def test_check_mode_never_mutates() -> None:
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, rec = _stub(base, eng, _meta(), existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="9.9.9.9/32"), check_mode=True)
    assert r.changed and not any(k == "mutate" for k, _ in rec)


def test_identity_unresolved_when_name_unset() -> None:
    base, eng = _engine_env()
    res, _ = _stub(base, eng, _meta(), existing=None)
    with pytest.raises(eng.IdentityUnresolved):
        res.apply(_Model(ip_netmask="1.1.1.1/32"))


def test_singleton_absent_raises() -> None:
    base, eng = _engine_env()
    res, _ = _stub(base, eng, _meta(singleton=True), existing=None)
    with pytest.raises(eng.AbsentNotSupported):
        res.absent(_Model(name="a"))


def test_absent_deletes_existing() -> None:
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, rec = _stub(base, eng, _meta(), existing=actual)
    r = res.absent(_Model(name="a"))
    assert r.changed and r.action == "deleted"
    assert ("delete", "1") in rec


def test_absent_missing_is_unchanged() -> None:
    base, eng = _engine_env()
    res, rec = _stub(base, eng, _meta(), existing=None)
    r = res.absent(_Model(name="a"))
    assert not r.changed and r.action == "unchanged"
    assert not any(k == "delete" for k, _ in rec)


def test_normalize_list_order_insensitive_by_default() -> None:
    base, eng = _engine_env()
    actual = _Model(name="a", tag=["x", "y"], id="1")
    meta = _meta(input_fields=["name", "tag"], order_sensitive=[])
    res, _ = _stub(base, eng, meta, existing=actual)
    r = res.apply(_Model(name="a", tag=["y", "x"]))
    assert not r.changed  # order-insensitive -> no drift
    meta2 = _meta(input_fields=["name", "tag"], order_sensitive=["tag"])
    res2, _ = _stub(base, eng, meta2, existing=actual)
    # order-sensitive -> drift
    assert res2.apply(_Model(name="a", tag=["y", "x"])).changed


def test_normalize_enum_value_and_nested() -> None:
    base, eng = _engine_env()

    class Color(enum.Enum):
        RED = "red"

    actual = _Model(name="a", color="red", nested={"k": ["1", "2"]}, id="1")
    meta = _meta(input_fields=["name", "color", "nested"])
    res, _ = _stub(base, eng, meta, existing=actual)
    r = res.apply(_Model(name="a", color=Color.RED, nested={"k": ["2", "1"]}))
    assert not r.changed  # enum -> value, nested list order-insensitive


def test_scope_excluded_from_diff() -> None:
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", folder="Shared", id="1")
    meta = _meta(
        scope={"fields": ["folder"], "rule": "exactly_one"},
        input_fields=["name", "ip_netmask", "folder"],
    )
    res, _ = _stub(base, eng, meta, existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32", folder="Prod"))
    assert not r.changed  # folder is scope, not drift


def test_sync_result_shape() -> None:
    base, eng = _engine_env()
    res, _ = _stub(base, eng, _meta(), existing=None)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32"))
    assert isinstance(r, eng.SyncResult)
    assert isinstance(r.diff, eng.Diff)
    assert r.before is None and isinstance(r.after, dict)
