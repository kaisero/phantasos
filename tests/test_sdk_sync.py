"""Unit tests for the vendored idempotent-sync runtime templates."""

import sys
import types

from phantasos.generator.sdk import render


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
    try:
        mod = types.ModuleType(f"_ip.extras.idempotency.{name}")
        mod.__package__ = "_ip.extras.idempotency"
        exec(compile(src, f"{name}.py", "exec"), mod.__dict__)  # noqa: S102
        sys.modules[f"_ip.extras.idempotency.{name}"] = mod
        return mod
    finally:
        pass  # left registered for dependent execs; cleaned per-test via fixture


def _render_idem(template: str, **params: object) -> str:
    return render._env().get_template(f"idempotency/{template}").render(**params)


def test_base_exposes_registries_and_protocols() -> None:
    mod = _exec_idem_module("base", _render_idem("base.py.jinja", federated=False), {})
    assert mod.FETCH == {} and mod.MUTATE == {} and mod.MATERIALIZE == {}
    for proto in ("FetchStrategy", "MutateStrategy", "MaterializeStrategy"):
        assert hasattr(mod, proto)
    assert issubclass(mod.NotFoundException, Exception)
