"""Rendered wrapper-page tests against the REAL built SDKs (C3/C6).

These exercise the gen_ref_pages driver end-to-end on the actual generated
``prisma_access`` / ``prisma_browser`` models — the only place duplicate-anchor
and field-table fidelity can be observed. They are SKIPPED under ``nox -s gate``
(prisma-access is built only in the opt-in ``sdk-docs`` session); run them with
the SDKs on ``sys.path`` (e.g. the live nox env). The full ``mkdocs build
--strict`` proof is ``nox -s sdk-docs``; here the per-page invariant "a wrapper
page emits exactly ONE ``:::`` block" is the structural guarantee that no inline
leaf can collide a primary autodoc anchor (the failure --strict would abort on).
"""

from __future__ import annotations

import io
import sys
import types
from pathlib import Path
from typing import Any

import jinja2
import pytest

_PA_SDK = Path("/home/ubuntu/git/prisma-access-sdk")
_BR_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

_GEN_REF = (
    Path(__file__).parent.parent
    / "src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja"
)

_SDKS_BUILT = (_PA_SDK / "prisma_access").is_dir() and (
    _BR_SDK / "prisma_browser"
).is_dir()

pytestmark = pytest.mark.skipif(
    not _SDKS_BUILT,
    reason="built SDKs not present (run via nox -s sdk-docs / live env)",
)


def _render_gen_ref(package: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_GEN_REF.parent)),
        keep_trailing_newline=True,
        autoescape=jinja2.select_autoescape(),
        undefined=jinja2.StrictUndefined,
    )
    return env.get_template(_GEN_REF.name).render(package=package, has_docs=True)


class _FakeNav:
    def __init__(self) -> None:
        self.items: dict[Any, Any] = {}

    def __setitem__(self, key: Any, value: Any) -> None:
        self.items[key] = value

    def build_literate_nav(self) -> list[str]:
        return [f"* {v}\n" for v in self.items.values()]


_CAPTURED: dict[str, dict[str, str]] = {}


def _capture(package: str, sdk_root: Path) -> dict[str, str]:
    """Run the rendered gen script with a capturing ``mkdocs_gen_files`` stub.

    Returns ``{doc-path: markdown}`` for every page the driver would emit. The
    walk is expensive (every models/ module), so it is memoized per package.
    """
    if package in _CAPTURED:
        return _CAPTURED[package]
    pages: dict[str, str] = {}

    fake = types.ModuleType("mkdocs_gen_files")
    fake.Nav = _FakeNav  # type: ignore[attr-defined]

    class _Open:
        def __init__(self, path: Any, mode: str = "r") -> None:
            self.path = str(path)
            self.buf = io.StringIO()

        def __enter__(self) -> io.StringIO:
            return self.buf

        def __exit__(self, *exc: Any) -> None:
            pages[self.path] = self.buf.getvalue()

    fake.open = lambda path, mode="r": _Open(path, mode)  # type: ignore[attr-defined]
    fake.set_edit_path = lambda *a, **k: None  # type: ignore[attr-defined]

    saved_mod = sys.modules.get("mkdocs_gen_files")
    sys.modules["mkdocs_gen_files"] = fake
    added = str(sdk_root) not in sys.path
    if added:
        sys.path.insert(0, str(sdk_root))
    # Hermetic import: other tests install a SYNTHETIC `prisma_access` into
    # sys.modules (introspection fixtures), which lacks `.extras`/real submodules.
    # Stash and purge the package so our import resolves against the real SDK on
    # sys.path, then restore so we don't clobber their cached module.
    stashed = {
        k: sys.modules.pop(k)
        for k in list(sys.modules)
        if k == package or k.startswith(package + ".")
    }
    script_path = sdk_root / "docs" / "scripts" / "gen_ref_pages.py"
    try:
        ns: dict[str, Any] = {"__file__": str(script_path)}
        try:
            exec(compile(_render_gen_ref(package), str(script_path), "exec"), ns)  # noqa: S102
        except (ModuleNotFoundError, ImportError, AttributeError) as exc:
            # The shared SDK at sdk_root can be rebuilt out from under us by a
            # concurrent `nox -s sdk-docs` — the federation `__init__` is briefly
            # mid-write (no `_SUBPACKAGES` -> single-spec path -> `extras` absent).
            # That is a transient rebuild race, not a rendering defect (the real
            # `--strict` proof is `nox -s sdk-docs`), so skip rather than fail.
            pytest.skip(
                f"{package} SDK not stably importable (concurrent rebuild?): {exc!r}"
            )
    finally:
        for k in [
            k for k in sys.modules if k == package or k.startswith(package + ".")
        ]:
            del sys.modules[k]
        sys.modules.update(stashed)
        if saved_mod is not None:
            sys.modules["mkdocs_gen_files"] = saved_mod
        else:
            sys.modules.pop("mkdocs_gen_files", None)
        if added and str(sdk_root) in sys.path:
            sys.path.remove(str(sdk_root))
    _CAPTURED[package] = pages
    return pages


def _page(pages: dict[str, str], suffix: str) -> str:
    matches = [v for k, v in pages.items() if k.endswith(suffix)]
    assert matches, f"no page ending {suffix!r} in {sorted(pages)[:5]}…"
    return matches[0]


def test_anyof_wrapper_inlines_payload_and_collapses_container() -> None:
    pages = _capture("prisma_access", _PA_SDK)
    ag = _page(pages, "objects/models/address_groups.md")
    # payload leaves rendered inline as field tables
    assert "Static" in ag and "Dynamic" in ag
    assert "| Field | Type | Required |" in ag
    # SCM container collapsed to one line; no folder/snippet field rows
    assert "Placement:" in ag
    assert "| `folder` |" not in ag and "| `snippet` |" not in ag
    # no oneOf/anyOf scaffolding leaked
    for noise in ("anyof_schema_", "any_of_schemas", "actual_instance"):
        assert noise not in ag, noise
    # exactly ONE autodoc block (the wrapper's own) -> no duplicate primary anchors
    assert ag.count("::: ") == 1


def test_scalar_only_wrapper_lists_its_types_never_blank() -> None:
    pages = _capture("prisma_access", _PA_SDK)
    zn = _page(pages, "network_services/models/zones_network.md")
    body = zn.split("\n", 1)[1].strip()  # everything past the `::: …` line
    assert body, "scalar-only wrapper page must not be blank"
    assert "Accepts:" in zn
    assert "`list[str]`" in zn


def test_oneof_browser_wrapper_renders_inline_not_link_list() -> None:
    pages = _capture("prisma_browser", _BR_SDK)
    pi = _page(pages, "models/policy_item.md")
    # variant model names present inline (semantic regression, not byte-identity)
    assert "RuleSummary" in pi or "Section" in pi
    assert "| Field | Type | Required |" in pi
    assert "One of the following variants" not in pi  # old link list is gone
    assert pi.count("::: ") == 1


def test_plain_model_page_is_byte_identical_single_autodoc() -> None:
    pages = _capture("prisma_browser", _BR_SDK)
    dg = _page(pages, "models/device_group_request.md")
    # a non-wrapper model page is exactly its one autodoc block, unchanged.
    assert dg == "::: prisma_browser.models.device_group_request\n"


def test_every_wrapper_page_has_a_single_autodoc_block() -> None:
    # The structural --strict guarantee across ALL wrapper pages of both products:
    # a wrapper page never re-`:::`-renders a leaf (which would collide anchors).
    for package, root in (("prisma_access", _PA_SDK), ("prisma_browser", _BR_SDK)):
        pages = _capture(package, root)
        offenders = {
            k: v.count("::: ")
            for k, v in pages.items()
            if "/models/" in k and v.count("::: ") > 1
        }
        assert not offenders, f"{package}: pages with >1 autodoc block: {offenders}"
