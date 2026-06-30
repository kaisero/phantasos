"""SDK build orchestrator: preprocess -> generate -> patch -> vendor -> scaffold.

Single-spec products run one preprocess -> generate -> patch -> vendor -> scaffold
pass. Federated products (``subpackages:``) instead loop that generate -> patch ->
vendor core once per sub-package (each emitted under ``<package>/<slug>/``), sharing
the ``_generate_one`` helper with the single-spec path, then scaffold the one
distribution. After the loop the runtime-hoist collapses the per-sub OAG runtimes
into one ``<package>/_runtime/``, the shared ``<package>/_auth.py`` is rendered, and
the composing ``<package>/__init__.py`` (``Client`` + ``_SUBPACKAGES``) is written
LAST to fuse the sub-packages into one client (see ``_build_federated``).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ...productconfig import HeaderSpec, LiveProbe, LoadedProduct

_ABOUT = '''\
"""Build provenance (written by phantasos)."""
SPEC_VERSION = {spec_version!r}
PHANTASOS_VERSION = {phantasos_version!r}
OPENAPI_GENERATOR_VERSION = {oag_version!r}
'''


def _phantasos_version() -> str:
    """The installed phantasos version, or ``"0+unknown"`` if not installed."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("phantasos")
    except PackageNotFoundError:
        return "0+unknown"


def _about_text(spec_version: str | None, oag_version: str) -> str:
    """Render ``_about.py`` with the REAL phantasos version (not a hardcoded lie)."""
    return _ABOUT.format(
        spec_version=spec_version,
        phantasos_version=_phantasos_version(),
        oag_version=oag_version,
    )


def build(loaded: LoadedProduct, *, run_smoke: bool = True) -> dict[str, Any]:
    from . import smoke

    cfg = loaded.config
    project_dir = loaded.output_dir
    stats: defaultdict[str, int] = defaultdict(int)

    if loaded.subpackages:
        result = _build_federated(loaded, project_dir, stats)
    else:
        result = _build_single(loaded, project_dir, stats)

    # Scaffold the distribution once (built-in + per-product overrides, overwrite).
    _scaffold(loaded, project_dir)

    # Smoke (federated: the parent `<package>` has no api/, so this is a no-op count
    # until P2 makes the import-walk per sub-package).
    result["smoke"] = smoke.smoke(str(project_dir), cfg.package, run=run_smoke)
    return result


def _generate_one(
    loaded: LoadedProduct,
    project_dir: Path,
    pp_path: Path,
    package: str,
    *,
    spec_version: str | None,
    context: dict[str, Any] | None = None,
    suppress_auth: bool = False,
    skip_validate_spec: bool = False,
    operations: dict[str, Any] | None = None,
    hook_mod: Any | None = None,
) -> tuple[Path, list[str], dict[str, int]]:
    """Generate -> patch -> vendor -> ``_about`` for one (preprocessed spec, package).

    Shared by the single-spec path and the federated loop (rev-2: extract, don't
    inline-duplicate). *package* may be dotted (``prisma_access.objects``), so the
    package dir is joined segment-wise. *distribution_root* for vendor is always
    *project_dir* — for single-spec that equals ``pkg_dir.parent`` (unchanged); for a
    nested sub-package it is the dir that must be on ``sys.path`` to import it.
    """
    from . import generate, render

    cfg = loaded.config
    generate.generate(
        str(pp_path),
        str(project_dir),
        package,
        library=cfg.generator.library,
        oneof_discriminator_lookup=cfg.generator.oneof_discriminator_lookup,
        skip_validate_spec=skip_validate_spec,
    )
    # Dotted-path fix: `prisma_access.objects` -> `<project_dir>/prisma_access/objects`
    # (a literal `project_dir / package` would make a `prisma_access.objects` dir).
    pkg_dir = project_dir / Path(*package.split("."))
    pkg_dir.mkdir(parents=True, exist_ok=True)

    patch_stats: dict[str, int] = {}
    if cfg.apply_generic_patches:
        from . import patches

        patch_stats = patches.apply_generic_patches(pkg_dir, package=package)
    if hook_mod is not None and hasattr(hook_mod, "patch"):
        hook_mod.patch(pkg_dir)

    vendored = render.vendor(
        pkg_dir,
        loaded,
        package=package,
        context=context,
        distribution_root=project_dir,
        suppress_auth=suppress_auth,
        operations=operations,
    )
    (pkg_dir / "_about.py").write_text(
        _about_text(spec_version, generate.OAG_VERSION),
        encoding="utf-8",
    )
    return pkg_dir, vendored, patch_stats


def _build_single(
    loaded: LoadedProduct, project_dir: Path, stats: defaultdict[str, int]
) -> dict[str, Any]:
    from . import generate, preprocess

    cfg = loaded.config

    # 1. preprocess: generic clean -> declarative transforms -> linked hook
    spec, yaml = preprocess.load(str(loaded.spec_path))
    preprocess.clean(spec, stats)
    if cfg.transforms.hoist:
        preprocess.hoist_items(
            spec,
            [(h.schema_name, h.field, h.item) for h in cfg.transforms.hoist],
            stats,
        )
    if cfg.transforms.tag_operations:
        preprocess.tag_operations(
            spec,
            [
                (t.path, t.method, t.operation_id, t.tag)
                for t in cfg.transforms.tag_operations
            ],
            stats,
        )
    hook_mod = _load_hooks(loaded)
    if hook_mod and hasattr(hook_mod, "preprocess"):
        hook_mod.preprocess(spec)

    pp_dir = project_dir / ".phantasos"
    pp_dir.mkdir(parents=True, exist_ok=True)
    pp_path = pp_dir / "preprocessed.yaml"
    preprocess.dump(spec, yaml, str(pp_path))
    spec_version = spec.get("info", {}).get("version")

    # 2-4. generate -> patch -> vendor -> _about (shared helper)
    generate.write_openapi_generator_ignore(project_dir)
    _pkg_dir, vendored, patch_stats = _generate_one(
        loaded,
        project_dir,
        pp_path,
        cfg.package,
        spec_version=spec_version,
        hook_mod=hook_mod,
    )
    generate.prune_suppressed_files(project_dir)

    return {"preprocess": dict(stats), "patches": patch_stats, "vendored": vendored}


def _build_federated(
    loaded: LoadedProduct, project_dir: Path, stats: defaultdict[str, int]
) -> dict[str, Any]:
    """Loop each sub-package through generate -> patch -> vendor under one distribution.

    Each sub owns its spec (``loaded.spec_path`` is ``None`` for federated — B5), so
    the spec is loaded inside the loop, never at the top level. Auth is suppressed
    per sub (``has_auth=False``, no shim): the shared composer is the auth/entry layer.
    """
    from . import generate, preprocess

    generate.write_openapi_generator_ignore(project_dir)  # once, before the loop

    pp_dir = project_dir / ".phantasos"
    pp_dir.mkdir(parents=True, exist_ok=True)

    vendored: dict[str, list[str]] = {}
    # spec-driven header scoping: per default_header, the slugs whose spec declares it
    # (as an in:header param) — the composer applies each header only to those subs.
    header_declared_by: dict[str, list[str]] = {
        name: [] for name in loaded.config.default_headers
    }
    # per-sub host overrides: a sub on a different gateway (e.g. ztna-connector on
    # api.sase while the rest are api.strata) gets a host-overridden config copy.
    host_overrides: dict[str, str] = {}
    for sub in loaded.subpackages:
        sub_spec, sub_yaml = preprocess.load(str(sub.spec_path))
        preprocess.clean(sub_spec, stats)  # incl. strip_external_tags
        # Derive this sub's host from its ORIGINAL servers (before fold pins them).
        sub_host = preprocess.resolve_sub_host(sub_spec, loaded.config.base_url)
        if sub_host != loaded.config.base_url:
            host_overrides[sub.config.slug] = sub_host
        # Fold each spec's servers[] domain prefix (/config/<domain>/v1) into its op
        # paths — the federated SDK shares ONE bare host, so a prefix left in servers
        # would be dropped and every call 404s (in-path-prefix specs are a no-op).
        preprocess.fold_server_prefix(sub_spec, loaded.config.base_url, stats)
        # SCM body reshape: restore the oneOf/anyOf payload OAG drops on configurable
        # objects, then drop server-assigned readOnly fields from `required` so create()
        # doesn't demand them. Both are guarded, top-level-schemas-only, no-op
        # elsewhere.
        preprocess.flatten_scm_bodies(sub_spec, stats)
        preprocess.relax_readonly_required(sub_spec, stats)
        # OAS `\p{}` Unicode-property patterns are invalid in Python's `re` (only the
        # 3rd-party `regex` supports them) -> the generated validator would PatternError
        # at deserialize time. Translate to Python-valid, permissive equivalents (e.g.
        # ztna's `^[\p{L}\p{N}\p{P}...]*$` response patterns).
        preprocess.translate_property_patterns(sub_spec, stats)
        norm = sub.config.normalize_operation_ids
        if norm is not None:
            preprocess.normalize_operation_ids(
                sub_spec,
                strip_suffix=norm.strip_suffix,
                dots_to_underscore=norm.dots_to_underscore,
                unify_separator=norm.unify_separator,
                stats=stats,
            )
        for hname in loaded.config.default_headers:
            if preprocess.spec_declares_header(sub_spec, hname):
                header_declared_by[hname].append(sub.config.slug)
        pp_path = pp_dir / f"{sub.config.slug}.yaml"
        preprocess.dump(sub_spec, sub_yaml, str(pp_path))
        spec_version = (sub_spec.get("info") or {}).get("version")

        _pkg_dir, sub_vendored, _patch_stats = _generate_one(
            loaded,
            project_dir,
            pp_path,
            sub.package,
            spec_version=spec_version,
            context=sub.context,
            suppress_auth=True,
            skip_validate_spec=sub.config.skip_validate_spec,
            operations=sub.config.operations,
        )
        vendored[sub.config.slug] = sub_vendored

    generate.prune_suppressed_files(project_dir)  # once, after the loop

    # P1.2: collapse each sub's OAG runtime ({api_client,configuration,rest,
    #   exceptions,api_response}.py) into one shared `<package>/_runtime/` and repoint
    #   every sub's runtime-targeting import to it (incl. each sub's __init__.py).
    from . import runtime

    runtime.hoist_runtime(
        project_dir,
        loaded.config.package,
        [s.config.slug for s in loaded.subpackages],
    )

    # P1.3: render the shared `<package>/_auth.py` (TokenManager + _BearerApiClient);
    #   the per-sub facades above are has_auth=False, so the composer owns auth.
    _render_shared_auth(loaded, project_dir)

    # P2.1: render the composer `<package>/__init__.py` (Client + _SUBPACKAGES),
    #   written LAST so it overwrites OAG's empty parent __init__. The first
    #   sub-facade it constructs wires retry onto the shared config (each facade
    #   self-wires `default_retry()` when `configuration.retries is None`).
    root = project_dir / Path(*loaded.config.package.split("."))
    (root / "__init__.py").write_text(
        _render_composer(
            [s.config.slug for s in loaded.subpackages],
            root_package=loaded.config.package,
            config_class_name=loaded.context["config_class_name"],
            headers=[
                {
                    "name": name,
                    "env": h.env,
                    "required": h.required,
                    "required_for": h.required_for,
                    "declared_by": header_declared_by[name],
                }
                for name, h in loaded.config.default_headers.items()
            ],
            host_overrides=host_overrides,
        ),
        encoding="utf-8",
    )

    return {"preprocess": dict(stats), "vendored": vendored}


def _render_composer(
    slugs: list[str],
    *,
    root_package: str,
    config_class_name: str,
    headers: list[dict[str, Any]] | None = None,
    host_overrides: dict[str, str] | None = None,
) -> str:
    """Render the composing ``<package>/__init__.py`` (Client + ``_SUBPACKAGES``).

    Direct render (no component model on disk, like ``_render_shared_auth``): the
    sub-package slugs + the distribution's ``root_package``/``config_class_name``
    drive ``facade/composer.py.jinja`` — absolute imports of the hoisted
    ``_runtime``, the shared ``_auth`` factories, and each sub's facade ``Client``.

    ``headers`` (declarative ``default_headers`` from sdk.yml) are applied on each
    ``_BearerApiClient`` handle from the environment at construction; a header with
    ``required``/``required_for`` raises if its env var is unset.
    """
    from . import render

    return (
        render._env()
        .get_template("facade/composer.py.jinja")
        .render(
            slugs=slugs,
            root_package=root_package,
            config_class_name=config_class_name,
            headers=headers or [],
            host_overrides=host_overrides or {},
        )
    )


def _render_shared_auth(loaded: LoadedProduct, project_dir: Path) -> None:
    """Render the ONE shared ``<package>/_auth.py`` for a federated distribution.

    Direct render (no component model on disk, like ``extras_init.py``): the auth
    component's fields + the product context drive the ``federated=True`` branch of
    ``auth/scm_oauth.py.jinja``, which imports the hoisted ``_runtime`` absolutely and
    attaches the bearer at the transport layer (``_BearerApiClient``). Dormant until
    the P2.1 composer imports it.
    """
    from . import render

    if loaded.auth is None:
        raise ValueError("federated product needs a top-level `auth:` block for _auth")
    fields = loaded.auth.model_dump()
    template = fields.pop("template")
    fields.pop("type", None)
    # has_retry=False: `retry.py` is a per-sub vendored extra (<slug>/extras/), not
    # hoisted to the package root, so the root-level _auth.py has no `.retry` sibling
    # to import. ponytail: the shared config skips auto-retry until the P2.1 composer
    # owns it — the per-sub facades keep their own retry.
    src = (
        render._env()
        .get_template(template)
        .render(**{**loaded.context, **fields, "federated": True, "has_retry": False})
    )
    root = project_dir / Path(*loaded.config.package.split("."))
    (root / "_auth.py").write_text(src, encoding="utf-8")


def _live_required_env(
    auth: Any | None, default_headers: dict[str, HeaderSpec]
) -> list[str]:
    """Env vars the emitted live smoke's skip-guard checks (auth creds + required
    region headers). Without any of these the composer raises a RuntimeError at
    construction/first-access, so the smoke must SKIP rather than ERROR. De-duped,
    order-preserving (auth creds first, then headers)."""
    env: list[str] = []
    if auth is not None and hasattr(auth, "credential_fields"):
        env += [cf.env_var for cf in auth.credential_fields() if cf.required]
    for header in default_headers.values():
        if header.required or header.required_for:
            env.append(header.env)
    deduped: list[str] = []
    for e in env:
        if e not in deduped:
            deduped.append(e)
    return deduped


def _validate_live_smoke(
    live_smoke: dict[str, LiveProbe],
    package: str,
    slugs: list[str],
    sdk_path: Path,
) -> None:
    """Fail-loud check of each ``live_smoke`` override against the BUILT SDK.

    The ``slug`` must be a known sub-package; an explicit ``object`` must be in that
    sub's ``_WRAPPERS`` and its ``verb`` a binding on that object. Reuses
    ``cli_operations`` (its ``object_attr``/``clean_method`` are the same
    ``_WRAPPERS``/``_bindings`` surface the runtime auto-pick reads) — no third
    introspector. An ``object``-less override is auto-picked at runtime, so there is
    nothing to validate at build time (skipped, no introspection)."""
    from ..cli.classify import cli_operations

    known = set(slugs)
    for slug, probe in live_smoke.items():
        if slug not in known:
            raise ValueError(
                f"live_smoke: sub-package {slug!r} is not in subpackages "
                f"({sorted(known)})"
            )
        if probe.object is None:
            continue  # auto-picked at runtime — nothing build-time to check
        inv = cli_operations(f"{package}.{slug}", sdk_path)
        verbs_by_obj: dict[str, set[str]] = {}
        for op in inv.operations:
            if op.object_attr is not None and op.clean_method is not None:
                verbs_by_obj.setdefault(op.object_attr, set()).add(op.clean_method)
        if probe.object not in verbs_by_obj:
            raise ValueError(
                f"live_smoke[{slug!r}]: object {probe.object!r} is not in {slug}'s "
                f"_WRAPPERS ({sorted(verbs_by_obj)})"
            )
        if probe.verb not in verbs_by_obj[probe.object]:
            raise ValueError(
                f"live_smoke[{slug!r}].{probe.object}: verb {probe.verb!r} is not a "
                f"binding ({sorted(verbs_by_obj[probe.object])})"
            )


def _live_smoke_context(loaded: LoadedProduct, project_dir: Path) -> dict[str, Any]:
    """Scaffold-context additions for the runtime federated live smoke.

    Single-spec products gate the template out (``federated=False`` -> whitespace ->
    skipped by ``render_scaffold``). Federated products validate any ``live_smoke``
    overrides against the just-built SDK (fail-loud) and bake the override map + the
    skip-guard env vars as Python literals."""
    cfg = loaded.config
    if not loaded.subpackages:
        return {
            "federated": False,
            "live_smoke_literal": "{}",
            "live_required_env_literal": "[]",
        }
    slugs = [s.config.slug for s in loaded.subpackages]
    _validate_live_smoke(cfg.live_smoke, cfg.package, slugs, project_dir)
    baked = {slug: probe.model_dump() for slug, probe in cfg.live_smoke.items()}
    required_env = _live_required_env(loaded.auth, cfg.default_headers)
    return {
        "federated": True,
        "live_smoke_literal": repr(baked),
        "live_required_env_literal": repr(required_env),
    }


def _scaffold(loaded: LoadedProduct, project_dir: Path) -> None:
    """Render the project scaffold (built-in + per-product overrides) once."""
    if loaded.config.project is None:
        raise ValueError(
            "sdk.yml needs a 'project:' block to scaffold the SDK; "
            "see docs/authoring.md"
        )
    readme_tpl = loaded.base_dir / "overrides" / "README.md.jinja"
    if not readme_tpl.exists():
        raise ValueError(
            f"missing {readme_tpl} — each product must provide a per-product README "
            "(overrides/README.md.jinja); see docs/authoring.md"
        )

    from ... import scaffold
    from . import docs as docs_stage

    overrides = loaded.base_dir / "overrides"
    context = dict(loaded.context)
    if loaded.config.docs is not None:
        context.update(docs_stage.build_docs_context(loaded, project_dir))
    context.update(_live_smoke_context(loaded, project_dir))
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        overrides if overrides.is_dir() else None,
        project_dir,
        context,
    )


def _load_hooks(loaded: LoadedProduct) -> Any | None:
    if not loaded.config.hooks:
        return None
    import importlib.util

    path = (loaded.base_dir / loaded.config.hooks).resolve()
    spec = importlib.util.spec_from_file_location("_phantasos_hooks", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load hooks from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
