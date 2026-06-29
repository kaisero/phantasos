"""The runtime federated live smoke: emission gate, baked literals, runtime
probe-resolution, and build-time `live_smoke` override validation.

The reviews flagged several ways a naive version becomes a green no-op, so these
tests exercise the EMITTED module's resolution logic against the real `fedsdk`
fixture (not just `ast.parse`): the auto-pick filters `requires == []` and calls
zero-arg, a no-probe sub fails cleanly (never a pre-HTTP ValueError/TypeError),
and `$ENV` args resolve at runtime. The file name MUST end `_live.py` or
`noxfile.py`'s `glob("tests/test_*_live.py")` never collects it.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from typing import Any, ClassVar

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from phantasos.config import ScmOAuth
from phantasos.generator.opmodel._pathutil import on_sys_path
from phantasos.generator.sdk.build import (
    _live_required_env,
    _validate_live_smoke,
)
from phantasos.productconfig import HeaderSpec, LiveProbe
from phantasos.scaffold import builtin_dir

FIXTURE = Path(__file__).parent / "fixtures" / "fedsdk"
_TEMPLATE = "test_federated_live.py.jinja"

_FED_CTX = {
    "federated": True,
    "package": "fedsdk",
    "live_smoke_literal": "{}",
    "live_required_env_literal": repr(
        ["CLIENT_ID", "CLIENT_SECRET", "SCOPE", "PANW_REGION"]
    ),
}


def _render(context: dict[str, Any]) -> str:
    """Render the single scaffold template the way `render_scaffold` would."""
    env = Environment(
        loader=FileSystemLoader(str(builtin_dir() / "tests")),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),
        undefined=StrictUndefined,
    )
    return env.get_template(_TEMPLATE).render(**context)


def _load(src: str, tmp_path: Path) -> Any:
    """Write the rendered smoke to disk and import it with `fedsdk` on sys.path."""
    f = tmp_path / "test_federated_live.py"
    f.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_emitted_live", f)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    with on_sys_path(FIXTURE):
        spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Emission gate + baked literals
# --------------------------------------------------------------------------- #
def test_template_emitted_name_ends_live() -> None:
    """The scaffold component renders to `tests/test_federated_live.py` — the
    `_live.py` suffix is what `noxfile.py`'s `glob` collects."""
    tpl = builtin_dir() / "tests" / _TEMPLATE
    assert tpl.exists()
    emitted = tpl.name[: -len(".jinja")]
    assert emitted == "test_federated_live.py"
    assert emitted.endswith("_live.py")


def test_single_spec_renders_whitespace_only() -> None:
    """A single-spec product renders to whitespace, so `render_scaffold` skips it —
    single-spec SDKs emit nothing new. Holds both when `federated` is explicitly
    False and when the key is absent (the generic full-scaffold render path)."""
    assert _render({**_FED_CTX, "federated": False}).strip() == ""
    assert _render({"package": "x"}).strip() == ""  # federated key absent


def test_federated_render_parses_and_has_safety_rails() -> None:
    src = _render(_FED_CTX)
    ast.parse(src)  # imports clean (syntax)
    assert "sorted(_sdk._SUBPACKAGES)" in src  # loops the registry
    assert "_FAIL_STATUSES = {404, 401, 424}" in src  # outcome rule
    assert "_request_timeout=" in src  # bounded timeout passed
    assert "limit=1" not in src  # zero-arg call, never a baked limit
    assert '["requires"] == []' in src  # auto-pick filters zero-arg lists
    assert "PANW_REGION" in src  # region var in the skip-guard
    assert "CLIENT_ID" in src and "SCOPE" in src


# --------------------------------------------------------------------------- #
# Runtime probe-resolution (against the real fedsdk fixture)
# --------------------------------------------------------------------------- #
def test_auto_pick_finds_zero_arg_list(tmp_path: Path) -> None:
    mod = _load(_render(_FED_CTX), tmp_path)
    with on_sys_path(FIXTURE):
        assert mod._auto_object(mod._wrappers("alpha")) == "widget"
        assert mod._resolve("alpha") == ("widget", "list", {})


def test_no_zero_arg_list_is_skipped_not_a_pre_http_error(tmp_path: Path) -> None:
    """A sub whose only list binding needs an arg (and no override) FAILS cleanly,
    never a pre-HTTP ValueError/TypeError that would bypass the status rule."""
    mod = _load(_render(_FED_CTX), tmp_path)

    class _IdOnly:
        _bindings: ClassVar[dict[str, Any]] = {
            "list": [{"raw_method": "get_thing", "requires": ["id"]}]
        }

    assert mod._auto_object({"thing": (_IdOnly, "things")}) is None
    mod._wrappers = lambda slug: {"thing": (_IdOnly, "things")}
    with pytest.raises(pytest.fail.Exception):
        mod._resolve("alpha")


def test_override_resolves_env_args_at_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load(_render(_FED_CTX), tmp_path)
    mod._LIVE_SMOKE = {
        "alpha": {
            "object": "widget",
            "verb": "get",
            "args": {"id": "$WIDGET_ID"},
            "skip": False,
        }
    }
    monkeypatch.setenv("WIDGET_ID", "w-42")
    with on_sys_path(FIXTURE):
        assert mod._resolve("alpha") == ("widget", "get", {"id": "w-42"})


def test_override_skip_skips(tmp_path: Path) -> None:
    mod = _load(_render(_FED_CTX), tmp_path)
    mod._LIVE_SMOKE = {
        "alpha": {"skip": True, "object": None, "verb": "list", "args": {}}
    }
    with pytest.raises(pytest.skip.Exception), on_sys_path(FIXTURE):
        mod._resolve("alpha")


# --------------------------------------------------------------------------- #
# Build-time override validation (fail-loud against the BUILT SDK)
# --------------------------------------------------------------------------- #
def test_validate_accepts_good_override() -> None:
    _validate_live_smoke(
        {"alpha": LiveProbe(object="widget", verb="get")},
        "fedsdk",
        ["alpha", "beta"],
        FIXTURE,
    )


def test_validate_auto_pick_needs_no_introspection() -> None:
    # object=None even with a nonsense verb is fine — auto-pick is a runtime concern.
    _validate_live_smoke(
        {"alpha": LiveProbe(verb="nope")}, "fedsdk", ["alpha", "beta"], FIXTURE
    )


def test_validate_rejects_unknown_slug() -> None:
    with pytest.raises(ValueError, match="gamma"):
        _validate_live_smoke(
            {"gamma": LiveProbe()}, "fedsdk", ["alpha", "beta"], FIXTURE
        )


def test_validate_rejects_unknown_object() -> None:
    with pytest.raises(ValueError, match="_WRAPPERS"):
        _validate_live_smoke(
            {"alpha": LiveProbe(object="sprocket")},
            "fedsdk",
            ["alpha", "beta"],
            FIXTURE,
        )


def test_validate_rejects_unknown_verb() -> None:
    with pytest.raises(ValueError, match="binding"):
        _validate_live_smoke(
            {"alpha": LiveProbe(object="widget", verb="compute")},
            "fedsdk",
            ["alpha", "beta"],
            FIXTURE,
        )


# --------------------------------------------------------------------------- #
# Skip-guard env derivation
# --------------------------------------------------------------------------- #
def test_required_env_is_auth_creds_plus_required_headers() -> None:
    auth = ScmOAuth(type="scm_oauth")
    headers = {
        "X-PANW-Region": HeaderSpec(env="PANW_REGION", required_for=["incidents"]),
        "prisma-tenant": HeaderSpec(env="PRISMA_TENANT", required=False),
    }
    assert _live_required_env(auth, headers) == [
        "CLIENT_ID",
        "CLIENT_SECRET",
        "SCOPE",
        "PANW_REGION",
    ]
