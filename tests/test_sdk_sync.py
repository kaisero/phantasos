"""Unit tests for the vendored idempotent-sync runtime templates."""

import enum
import sys
import types
from collections.abc import Iterator
from types import SimpleNamespace
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
    # A nested strategy (e.g. `fetch.list_scan`) needs its intermediate package
    # (`_ip.extras.idempotency.fetch`) present so its `..base` relative import
    # resolves one level up to `_ip.extras.idempotency.base`.
    parent = fqname.rsplit(".", 1)[0]
    if parent not in sys.modules:
        sub = types.ModuleType(parent)
        sub.__path__ = []
        sys.modules[parent] = sub
    mod = types.ModuleType(fqname)
    mod.__package__ = parent
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


# --- strategy modules (fetch/mutate/materialize) -----------------------------


def _exec_strategy(
    family: str, name: str, base: types.ModuleType, eng: types.ModuleType
) -> types.ModuleType:
    src = _render_idem(f"{family}/{name}.py.jinja", federated=False)
    deps = {
        "_ip.extras.idempotency.base": base,
        "_ip.extras.idempotency.engine": eng,
    }
    return _exec_idem_module(f"{family}.{name}", src, deps)


class _Page:
    def __init__(self, data: list[Any]) -> None:
        self.data = data


def test_list_scan_absorbs_404_and_empty_and_matches() -> None:
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)
    meta = _meta(fetch="list_scan")

    # 404 -> None
    class R404:
        def list(self, **kw: object) -> object:
            raise base.NotFoundException()

        _full = eng.SyncMixin._full

    assert ls.list_scan(R404(), {"name": "a"}, {}, meta) is None

    # empty -> None
    class REmpty:
        def list(self, **kw: object) -> object:
            return _Page([])

        _full = eng.SyncMixin._full

    assert ls.list_scan(REmpty(), {"name": "a"}, {}, meta) is None
    # exact match
    hit = _Model(name="a", id="1")

    class RHit:
        def list(self, **kw: object) -> object:
            return _Page([_Model(name="b", id="2"), hit])

        _full = eng.SyncMixin._full

    assert ls.list_scan(RHit(), {"name": "a"}, {}, meta) is hit


def test_list_scan_raises_on_multiple_matches() -> None:
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)

    class RDup:
        def list(self, **kw: object) -> object:
            return _Page([_Model(name="a", id="1"), _Model(name="a", id="2")])

        _full = eng.SyncMixin._full

    with pytest.raises(eng.IdentityUnresolved):
        ls.list_scan(RDup(), {"name": "a"}, {}, _meta(fetch="list_scan"))


def test_list_scan_hydrates_when_opted() -> None:
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)
    got = _Model(name="a", id="1", description="full")

    class RHyd:
        def list(self, **kw: object) -> object:
            return _Page([_Model(name="a", id="1")])

        def get(self, *, id: object) -> object:
            return got

        _full = eng.SyncMixin._full

    meta = _meta(fetch="list_scan", fetch_opts={"page_limit": 200, "hydrate": True})
    assert ls.list_scan(RHyd(), {"name": "a"}, {}, meta) is got


def test_list_filter_hydrates_via_get() -> None:
    base, eng = _engine_env()
    lf = _exec_strategy("fetch", "list_filter", base, eng)
    got = _Model(name="a", id="1", description="full")
    seen: dict[str, object] = {}

    class RHyd:
        def list(self, **kw: object) -> object:
            seen["list_kw"] = kw
            return _Page([_Model(name="a", id="1")])

        def get(self, *, id: object) -> object:
            seen["get_id"] = id
            return got

        _full = eng.SyncMixin._full

    meta = _meta(fetch="list_filter", fetch_opts={"hydrate": True})
    assert lf.list_filter(RHyd(), {"name": "a"}, {"folder": "Shared"}, meta) is got
    # identity + scope both flow to the server-side list filter
    assert seen["list_kw"] == {"name": "a", "folder": "Shared"}
    assert seen["get_id"] == "1"


def test_list_filter_absorbs_404_and_empty() -> None:
    base, eng = _engine_env()
    lf = _exec_strategy("fetch", "list_filter", base, eng)
    meta = _meta(fetch="list_filter")

    class R404:
        def list(self, **kw: object) -> object:
            raise base.NotFoundException()

        _full = eng.SyncMixin._full

    assert lf.list_filter(R404(), {"name": "a"}, {}, meta) is None

    class REmpty:
        def list(self, **kw: object) -> object:
            return _Page([])

        _full = eng.SyncMixin._full

    assert lf.list_filter(REmpty(), {"name": "a"}, {}, meta) is None


def test_put_rmw_seeds_actual_overlays_desired_drops_id() -> None:
    base, eng = _engine_env()
    pr = _exec_strategy("mutate", "put_rmw", base, eng)
    calls: dict[str, object] = {}
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", description="keep", id="1")

    class R:
        _present = eng.SyncMixin._present

        def replace(self, *, id: object, body: object) -> object:
            calls["id"] = id
            calls["body"] = body
            return body

    desired = _Model(name="a", ip_netmask="2.2.2.2/32")
    body = pr.put_rmw(R(), desired, actual, None, _meta())
    assert calls["id"] == "1"
    dumped = body.model_dump()
    assert dumped["ip_netmask"] == "2.2.2.2/32" and dumped["description"] == "keep"
    assert "id" not in dumped


def test_patch_minimal_sends_only_changed_in_patch_model() -> None:
    base, eng = _engine_env()
    pm = _exec_strategy("mutate", "patch_minimal", base, eng)
    calls: dict[str, object] = {}

    class R:
        def update(self, *, id: object, body: _Model) -> _Model:
            calls["id"] = id
            calls["body"] = body
            return body

    diff = eng.Diff(True, {"description": {"before": "old", "after": "new"}})
    meta = _meta(mutate="patch_minimal", update={"verb": "update"})
    actual = _Model(name="a", id="1")
    pm.patch_minimal(R(), _Model(name="a", description="new"), actual, diff, meta)
    assert calls["id"] == "1"
    body = calls["body"]
    assert isinstance(body, _Model)
    assert body.model_dump() == {"description": "new"}


def test_direct_returns_response() -> None:
    base, eng = _engine_env()
    d = _exec_strategy("materialize", "direct", base, eng)
    obj = _Model(name="a", id="1")
    assert d.direct(object(), obj, {}, {}, _meta()) is obj


def test_get_after_write_reads_id_then_gets() -> None:
    base, eng = _engine_env()
    gaw = _exec_strategy("materialize", "get_after_write", base, eng)
    fresh = _Model(name="a", id="1", description="full")

    class R:
        def get(self, *, id: object) -> object:
            assert id == "1"
            return fresh

    envelope = _Model(id="1")
    assert gaw.get_after_write(R(), envelope, {}, {}, _meta()) is fresh


# --- integration: the six real strategies through SyncMixin end-to-end --------


def _register_all(base: types.ModuleType, eng: types.ModuleType) -> None:
    """Exec the six strategy modules so they self-register into base's registries."""
    for family, name in (
        ("fetch", "list_scan"),
        ("fetch", "list_filter"),
        ("mutate", "put_rmw"),
        ("mutate", "patch_minimal"),
        ("materialize", "direct"),
        ("materialize", "get_after_write"),
    ):
        _exec_strategy(family, name, base, eng)


def _access_meta(**over: object) -> dict[str, object]:
    """prisma-access shape: list_scan fetch, put_rmw (replace), direct materialize."""
    return _meta(
        fetch="list_scan",
        mutate="put_rmw",
        materialize="direct",
        update={"verb": "replace"},
        **over,
    )


def test_integration_list_scan_absence_shapes_to_none() -> None:
    base, eng = _engine_env()
    _register_all(base, eng)

    class Stub404(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = _access_meta()

        def list(self, **kw: object) -> object:
            raise base.NotFoundException()

    class StubEmpty(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = _access_meta()

        def list(self, **kw: object) -> object:
            return _Page([])

    assert Stub404().fetch(name="a") is None
    assert StubEmpty().fetch(name="a") is None


def test_integration_create_materializes_direct() -> None:
    base, eng = _engine_env()
    _register_all(base, eng)

    class Stub(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = _access_meta()

        def list(self, **kw: object) -> object:
            return _Page([])  # absent -> create

        def create(self, *, body: _Model) -> object:
            return _Model(id="new", **body.model_dump())  # response IS the object

    r = Stub().apply(_Model(name="a", ip_netmask="1.1.1.1/32"))
    assert r.changed and r.action == "created"
    assert r.after["name"] == "a" and r.after["id"] == "new"


def test_integration_update_put_rmw_preserves_unmanaged() -> None:
    base, eng = _engine_env()
    _register_all(base, eng)
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", description="keep", id="1")

    class Stub(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = _access_meta()

        def list(self, **kw: object) -> object:
            return _Page([actual])

        def replace(self, *, id: object, body: _Model) -> object:
            return _Model(**{**body.model_dump(), "id": id})  # response IS the object

    r = Stub().apply(_Model(name="a", ip_netmask="2.2.2.2/32"))
    assert r.changed and r.action == "updated"
    assert r.after["ip_netmask"] == "2.2.2.2/32"
    assert r.after["description"] == "keep"  # unmanaged field preserved by RMW


def test_integration_check_mode_writes_nothing() -> None:
    base, eng = _engine_env()
    _register_all(base, eng)
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    wrote: list[str] = []

    class Stub(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = _access_meta()

        def list(self, **kw: object) -> object:
            return _Page([actual])

        def replace(self, *, id: object, body: object) -> object:
            wrote.append("replace")
            return actual

    r = Stub().apply(_Model(name="a", ip_netmask="9.9.9.9/32"), check_mode=True)
    assert r.changed and not wrote


def test_integration_browser_shape_get_after_write_and_patch() -> None:
    base, eng = _engine_env()
    _register_all(base, eng)
    # prisma-browser shape: list_filter fetch (hydrate), patch_minimal, get_after_write
    meta = _meta(
        fetch="list_filter",
        mutate="patch_minimal",
        materialize="get_after_write",
        update={"verb": "update"},
        fetch_opts={"hydrate": True},
    )
    store: dict[str, _Model] = {}

    class Stub(eng.SyncMixin):  # type: ignore[name-defined,misc]
        _idempotency = meta

        def list(self, **kw: object) -> object:
            return _Page([store[k] for k in store])

        def get(self, *, id: object) -> object:
            return store[id]  # type: ignore[index]

        def create(self, *, body: _Model) -> object:
            store["1"] = _Model(id="1", **body.model_dump())
            return _Model(id="1")  # id-only envelope

        def update(self, *, id: object, body: _Model) -> object:
            cur = store[id]  # type: ignore[index]
            store[id] = _Model(**{**cur.model_dump(), **body.model_dump()})  # type: ignore[index]
            return _Model(id=id)  # envelope

    s = Stub()
    r = s.apply(_Model(name="a", description="orig"))
    assert r.action == "created" and r.after["description"] == "orig"  # GET-after
    r = s.apply(_Model(name="a", description="new"))
    # PATCH-minimal + GET-after materializes the updated state
    assert r.action == "updated" and r.after["description"] == "new"


# --- resource-wrapper template wiring (resource.py.jinja) ---------------------


def _object_view(*, sync: bool, idempotency_literal: str = "{}") -> SimpleNamespace:
    """Minimal ObjectView-shaped namespace the resource template can render."""
    return SimpleNamespace(
        classname="AddressResource",
        attr="address",
        api_cls="AddressApi",
        api_module="address_api",
        bindings_literal="{}",
        methods=[],
        sync=sync,
        idempotency_literal=idempotency_literal,
    )


def _render_resource(objects: list[SimpleNamespace], **params: object) -> str:
    return (
        render._env()
        .get_template("facade/resource.py.jinja")
        .render(objects=objects, imports=[], **params)
    )


def test_resource_renders_syncmixin_and_classvar_when_opted() -> None:
    src = _render_resource(
        [_object_view(sync=True, idempotency_literal='{"identity": ["name"]}')],
        has_pagination=True,
        has_idempotency=True,
    )
    assert "from .idempotency import SyncMixin" in src
    assert "class AddressResource(SyncMixin):" in src
    assert "_idempotency: ClassVar[dict[str, Any]] =" in src


def test_resource_render_byte_identical_when_off() -> None:
    off = _render_resource(
        [_object_view(sync=False)],
        has_pagination=True,
        has_idempotency=False,
    )
    assert "SyncMixin" not in off
    assert "_idempotency" not in off
