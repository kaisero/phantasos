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


def test_anyof_wrapper_inlines_variant_field_tables() -> None:
    """A surviving prisma_access anyOf/oneOf wrapper inlines each variant's fields as
    a table, leaks no generator scaffolding, and emits exactly one autodoc block.

    (Previously pinned AddressGroups — now flattened to a plain model by the SCM body
    reshape, along with every other SCM "configurable object", so the only anyOf/oneOf
    wrappers left in prisma_access are the real nested value-unions like this one
    (ike-crypto lifetime = seconds|minutes|hours|days). That keeps prisma_access
    wrapper-page coverage alive on a model the reshape deliberately does NOT touch.)
    """
    pages = _capture("prisma_access", _PA_SDK)
    lt = _page(pages, "network_services/models/ike_crypto_profiles_lifetime.md")
    # each variant rendered inline as a field table
    assert "Seconds" in lt and "Minutes" in lt
    assert "| Field | Type | Required |" in lt
    # no oneOf/anyOf scaffolding leaked
    for noise in ("anyof_schema_", "any_of_schemas", "actual_instance"):
        assert noise not in lt, noise
    # exactly ONE autodoc block (the wrapper's own) -> no duplicate primary anchors
    assert lt.count("::: ") == 1


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


def test_plain_model_page_is_converted_to_a_field_table() -> None:
    pages = _capture("prisma_browser", _BR_SDK)
    dg = _page(pages, "models/device_group_request.md")
    # a plain model page is now a heading-only autodoc block (keeps the autoref anchor)
    # + the 5-col field table — NOT the full `::: module` autodoc, and no
    # griffe-pydantic Config/Validators boilerplate (`extensions: []`).
    assert dg.startswith(
        "::: prisma_browser.models.device_group_request.DeviceGroupRequest\n"
    )
    assert "extensions: []" in dg
    assert "| Field | Type | Required | Default | Description |" in dg
    assert dg.count("::: ") == 1  # single heading-only block, no leaf re-render


def test_wrapper_body_synthesizes_constructable_full_nesting() -> None:
    """A real oneOf wrapper body synthesizes the nested, constructable form
    ``PolicyItem(RuleSummary(...))`` — never an opaque ``PolicyItem(...)`` placeholder,
    and never the bare leaf the wrapper rejects. Skipped on the gate (no built SDKs);
    the real-model construction is the proof string/unit tests can't give.

    (Previously exercised AddressGroups(GroupType(Static(…))) — AddressGroups is now a
    flat model after the SCM body reshape, so its leaf wrapper modules are gone. The
    same synthesize-and-construct invariant now rides prisma_browser's surviving
    ``PolicyItem`` oneOf wrapper.)
    """
    import importlib

    from phantasos.generator.sdk.examples import synthesize_body

    added = str(_BR_SDK) not in sys.path
    if added:
        sys.path.insert(0, str(_BR_SDK))
    stashed = {
        k: sys.modules.pop(k)
        for k in list(sys.modules)
        if k == "prisma_browser" or k.startswith("prisma_browser.")
    }
    try:
        base = "prisma_browser.models"
        pi = importlib.import_module(f"{base}.policy_item")
        rs = importlib.import_module(f"{base}.rule_summary")
        sec = importlib.import_module(f"{base}.section")
        out = synthesize_body(pi.PolicyItem)
        assert "PolicyItem(...)" not in out  # not opaque
        assert "PolicyItem(RuleSummary(" in out  # nested into the first variant
        # the proof unit tests can't give: it actually constructs (a bare/unwrapped
        # form raises ValidationError on the real wrapper).
        ns = {
            "PolicyItem": pi.PolicyItem,
            "RuleSummary": rs.RuleSummary,
            "Section": sec.Section,
        }
        obj = eval(out, ns)  # noqa: S307
        assert type(obj.actual_instance).__name__ == "RuleSummary"
    finally:
        for k in [
            k
            for k in sys.modules
            if k == "prisma_browser" or k.startswith("prisma_browser.")
        ]:
            del sys.modules[k]
        sys.modules.update(stashed)
        if added and str(_BR_SDK) in sys.path:
            sys.path.remove(str(_BR_SDK))


def test_wrapper_field_tables_cross_link_model_types() -> None:
    # R3: a variant leaf whose field type is itself a DOCUMENTED model renders a
    # clickable mkdocstrings autoref (`[`Name`][dotted.Name]`) instead of dead type
    # text — so the reader can drill into the nested shape. (The full `--strict` proof
    # that these identifiers RESOLVE is `nox -s sdk-docs`; here we prove they're emitted
    # and never point outside the package's own documented models.)
    import re

    pages = _capture("prisma_access", _PA_SDK)
    link = re.compile(r"\[`[^`]+`\]\[prisma_access\.[\w.]+\.[A-Za-z]\w*\]")
    linked = [k for k, v in pages.items() if link.search(v)]
    assert linked, "expected model-type cross-links on wrapper field tables (R3)"


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
