"""Vendor step: render selected component templates into the SDK's extras/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...productconfig import LoadedProduct

if TYPE_CHECKING:
    from jinja2 import Environment

_COMPONENTS_DIR = Path(__file__).parent / "components"
_IMPORT_RE = re.compile(r"^from \S+\.api\.(\w+) import (\w+)\s*$", re.M)


def _env() -> Environment:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    # Templates render Python source, not HTML. select_autoescape() only escapes
    # .html/.xml names (we have none), so generated code is never HTML-mangled
    # (e.g. `>` -> `&gt;`) — and it satisfies the autoescape security lint.
    return Environment(
        loader=FileSystemLoader(str(_COMPONENTS_DIR)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),
    )


def _discover_resources(pkg_dir: Path) -> list[dict[str, str]]:
    """[{attr, module, cls}] from the generated api/__init__.py import lines."""
    init = (pkg_dir / "api" / "__init__.py").read_text(encoding="utf-8")
    out: list[dict[str, str]] = []
    for module, cls in _IMPORT_RE.findall(init):
        out.append(
            {
                "module": module,
                "cls": cls,
                "attr": module[:-4] if module.endswith("_api") else module,
            }
        )
    return out


def vendor(
    pkg_dir: Path,
    loaded: LoadedProduct,
    *,
    package: str | None = None,
    context: dict[str, Any] | None = None,
    distribution_root: Path | None = None,
    suppress_auth: bool = False,
    operations: dict[str, Any] | None = None,
    idempotency: Any | None = None,
    wrapper_objects: list[Any] | None = None,
) -> list[str]:
    """Render the selected component templates into ``<pkg>/extras/``.

    When the facade is enabled the object-granular typed resource wrappers are
    also emitted (``extras/resources.py``). *wrapper_objects* may supply a
    pre-built ``build_wrapper_context`` result (the stub-package component tests
    pass ``[]`` to opt out of live introspection); otherwise the freshly
    generated package is introspected to build it.

    Federated sub-packages pass *package*/*context*/*distribution_root* directly
    (the sub's dotted import path, its per-sub jinja context, and the
    distribution root that must be on ``sys.path`` to import the nested package);
    single-spec callers omit them and default to ``loaded.config.package`` /
    ``loaded.context`` / ``pkg_dir.parent`` (unchanged). *suppress_auth* forces
    ``has_auth=False`` and skips writing ``auth.py`` — the sub facade is then a
    self-contained ``Client(api_client)`` whose bearer is injected by the shared
    composer (P1.3/P2.1); no ``from <pkg>._auth import …`` shim is written (it
    would ImportError during this loop's introspection).
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    pkg = package or loaded.config.package
    dist_root = distribution_root or pkg_dir.parent
    # Per-sub `operations:` overrides (federated) vs the product's top-level block
    # (single-spec). build_wrapper_context's validate_override_keys rejects keys
    # absent from THIS package's inventory, so a federated sub must pass its OWN
    # overrides — a top-level key for another sub's op would fail every other sub.
    ops = operations if operations is not None else loaded.config.operations
    extras = pkg_dir / "extras"
    extras.mkdir(exist_ok=True)
    written: list[str] = []
    ctx = dict(context) if context is not None else dict(loaded.context)

    builtin_env = _env()
    product_env = Environment(
        loader=FileSystemLoader(str(loaded.base_dir)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),  # renders Python source, not HTML
    )

    def render_template(template: str, **extra: Any) -> str:
        merged = {**ctx, **extra}
        if Path(template).is_absolute():
            rel = Path(template).relative_to(loaded.base_dir)
            return product_env.get_template(str(rel)).render(**merged)
        return builtin_env.get_template(template).render(**merged)

    def write_component(name: str, component: Any, **extra: Any) -> None:
        fields = component.model_dump()
        template = fields.pop("template")
        fields.pop("type", None)
        (extras / name).write_text(render_template(template, **{**fields, **extra}), encoding="utf-8")
        written.append(name)

    if suppress_auth:
        # Federated sub: the facade self-contains; the composer is the auth/entry
        # layer (P1.3/P2.1). Force has_auth=False so the facade + extras/__init__
        # (both gate on `{% if has_auth %}`) emit no `from .auth` import, and skip
        # writing auth.py. Rebinds ctx — the render_template/write_component
        # closures read it fresh, so later renders see has_auth=False.
        ctx = {**ctx, "has_auth": False}
    elif loaded.auth:
        write_component("auth.py", loaded.auth)
    if loaded.pagination:
        write_component("pagination.py", loaded.pagination)
    if loaded.errors:
        write_component("errors.py", loaded.errors)
    if loaded.facade:
        # Pass 1: raw-`*Api` facade (exposes `_RESOURCES`, NO wrapper imports) so
        # the package is importable and introspect(...) can read `_RESOURCES`.
        write_component("facade.py", loaded.facade, resources=_discover_resources(pkg_dir))
    if loaded.retry:
        write_component("retry.py", loaded.retry)

    for dest, source in loaded.config.include.items():
        target = (extras / dest).resolve()
        if not target.is_relative_to(extras.resolve()):
            raise ValueError(f"include destination {dest!r} escapes extras/")
        target.parent.mkdir(parents=True, exist_ok=True)
        rel = (loaded.base_dir / source).resolve().relative_to(loaded.base_dir)
        target.write_text(product_env.get_template(str(rel)).render(**ctx), encoding="utf-8")
        written.append(dest)

    (extras / "__init__.py").write_text(
        builtin_env.get_template("extras_init.py.jinja").render(**ctx), encoding="utf-8"
    )
    written.append("__init__.py")

    # Resources are vendored LAST: introspecting the package imports `extras`
    # (and through it auth/errors/facade/retry/pagination), all of which must
    # already exist on disk.
    if loaded.facade:
        objects = _vendor_resources(
            pkg_dir,
            loaded,
            pkg,
            dist_root,
            ops,
            extras,
            builtin_env,
            written,
            wrapper_objects,
            idempotency,
        )
        if idempotency is not None:
            # Vendor the idempotency engine + the union of referenced strategy
            # modules BEFORE the pass-2 facade render, so `resources.py`'s
            # `from .idempotency import SyncMixin` resolves on import. `objects`
            # already carry the baked `_idempotency_meta` (resolve_idempotency ran
            # inside build_wrapper_context).
            _vendor_idempotency(pkg_dir, objects, ctx, builtin_env, written)
        # Pass 2: RE-render the facade in full now that `resources.py` exists —
        # bind `client.<object>` to the typed wrappers (sharing one `*Api`
        # instance per backing class), keep `_RESOURCES`, add `_WRAPPERS`.
        write_component(
            "facade.py",
            loaded.facade,
            resources=_discover_resources(pkg_dir),
            wrappers=True,
            objects=objects,
        )
        # Pass 1's introspection imported `<pkg>`, `<pkg>.extras`,
        # `<pkg>.extras.facade` (and possibly `.resources`) into THIS process's
        # `sys.modules`. Pass 2 just rewrote `facade.py` on disk, so any later
        # in-process import would resurrect the STALE pass-1 facade (no
        # `_WRAPPERS`). Drop those entries so the next import re-reads disk.
        _invalidate_pkg_modules(pkg)
    return written


def _invalidate_pkg_modules(package: str) -> None:
    """Drop the vendored package's cached modules from this process's import cache.

    Removes ``<package>``, ``<package>.extras`` and any ``<package>.extras.*``
    (e.g. ``facade``/``resources``) so a later import re-reads the rewritten
    pass-2 ``facade.py`` instead of the stale pass-1 module object.
    """
    import sys

    for name in list(sys.modules):
        if name == package or name == f"{package}.extras" or name.startswith(f"{package}.extras."):
            del sys.modules[name]


def _vendor_resources(
    pkg_dir: Path,
    loaded: LoadedProduct,
    pkg: str,
    dist_root: Path,
    operations: dict[str, Any],
    extras: Path,
    env: Environment,
    written: list[str],
    wrapper_objects: list[Any] | None,
    idempotency: Any | None = None,
) -> list[Any]:
    """Render the object-granular typed resource wrappers into ``resources.py``.

    Uses *wrapper_objects* when supplied; otherwise introspects the
    freshly-vendored package (the pass-1 ``facade.py`` — and thus ``_RESOURCES``
    — is already written) to build the context. *pkg* is the (possibly dotted)
    import path and *dist_root* the directory that must be on ``sys.path`` to
    import it — for a federated sub these are ``prisma_access.<slug>`` and the
    distribution root (``project_dir``), not ``pkg_dir.parent``. The per-object
    imports are merged + sorted for a stable, ruff-clean import block. Returns
    the ``ObjectView`` list so the caller can drive the pass-2 facade re-render.
    """
    objects = wrapper_objects
    if objects is None:
        from ..opmodel import introspect
        from .wrapper import build_wrapper_context

        inv = introspect(pkg, dist_root)
        objects = build_wrapper_context(
            inv,
            operations,
            _discover_resources(pkg_dir),
            docs=loaded.config.docs,
            idempotency=idempotency,
            dist_root=dist_root,
            has_pagination=loaded.pagination is not None,
        )
    imports: set[tuple[str, str]] = set()
    for o in objects:
        imports |= o.imports
    src = env.get_template("facade/resource.py.jinja").render(
        objects=objects,
        imports=sorted(imports),
        has_pagination=loaded.pagination is not None,
        has_idempotency=any(getattr(o, "sync", False) for o in objects),
    )
    (extras / "resources.py").write_text(src, encoding="utf-8")
    written.append("resources.py")
    return objects


def _vendor_idempotency(
    pkg_dir: Path,
    objects: list[Any],
    ctx: dict[str, Any],
    env: Environment,
    written: list[str],
) -> None:
    """Vendor ``extras/idempotency/`` — the engine plus the UNION of referenced
    strategy modules — when at least one object opts into idempotent sync.

    Writes ``base.py`` + ``engine.py`` (the seams/registries + the SyncMixin
    orchestrator), the ``fetch``/``mutate``/``materialize`` family subpackages
    holding ONLY the strategy modules named in
    :func:`~.idempotency.referenced_strategies` (an empty family is skipped
    entirely), and a top-level ``__init__.py`` that re-exports the engine surface
    and imports each vendored strategy module so its ``FETCH``/``MUTATE``/
    ``MATERIALIZE`` self-registration runs at import time. Purely additive: a
    product with no synced objects gets no ``extras/idempotency/`` at all.
    """
    from .idempotency import referenced_strategies

    refs = referenced_strategies(objects)
    if not any(refs.values()):
        return
    idem = pkg_dir / "extras" / "idempotency"
    idem.mkdir(parents=True, exist_ok=True)
    for core in ("base", "engine"):
        (idem / f"{core}.py").write_text(
            env.get_template(f"idempotency/{core}.py.jinja").render(**ctx),
            encoding="utf-8",
        )
    for family in ("fetch", "mutate", "materialize"):
        names = sorted(refs[family])
        if not names:
            continue
        (idem / family).mkdir(exist_ok=True)
        # The family subpackage is a plain namespace: the strategy submodules are
        # imported by name from extras/idempotency/__init__.py, so an empty
        # __init__ suffices (`from .fetch import list_scan` loads the submodule).
        (idem / family / "__init__.py").write_text("", encoding="utf-8")
        for name in names:
            (idem / family / f"{name}.py").write_text(
                env.get_template(f"idempotency/{family}/{name}.py.jinja").render(**ctx),
                encoding="utf-8",
            )
    (idem / "__init__.py").write_text(
        env.get_template("idempotency/__init__.py.jinja").render(
            fetch=sorted(refs["fetch"]),
            mutate=sorted(refs["mutate"]),
            materialize=sorted(refs["materialize"]),
            **ctx,
        ),
        encoding="utf-8",
    )
    written.append("idempotency/")
