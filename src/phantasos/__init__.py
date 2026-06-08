"""phantasos — generate native, self-contained Python SDKs from OpenAPI specs.

Public API: `build(loaded)`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .config import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
)
from .productconfig import LoadedProduct

__all__ = [
    "CursorPagination",
    "Facade",
    "NestedError",
    "OAuthClientCredentials",
    "build",
]

_ABOUT = '''\
"""Build provenance (written by phantasos)."""
SPEC_VERSION = {spec_version!r}
PHANTASOS_VERSION = {phantasos_version!r}
OPENAPI_GENERATOR_VERSION = {oag_version!r}
'''


def build(loaded: LoadedProduct, *, run_smoke: bool = True) -> dict[str, Any]:
    from . import generate, preprocess, render, smoke

    cfg = loaded.config
    project_dir = loaded.output_dir
    stats: defaultdict[str, int] = defaultdict(int)

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

    # 2. generate
    generate.write_openapi_generator_ignore(project_dir)
    generate.generate(str(pp_path), str(project_dir), cfg.package, library=cfg.library)
    generate.prune_suppressed_files(project_dir)
    pkg_dir = project_dir / cfg.package
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # 3. patches: generic -> linked hook
    patch_stats: dict[str, int] = {}
    if cfg.apply_generic_patches:
        from . import patches

        patch_stats = patches.apply_generic_patches(pkg_dir)
    if hook_mod and hasattr(hook_mod, "patch"):
        hook_mod.patch(pkg_dir)

    # 4. vendor
    vendored = render.vendor(pkg_dir, loaded)

    # 4b. scaffold the project (built-in + per-product overrides, overwrite)
    from . import scaffold

    overrides = loaded.base_dir / "overrides"
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        overrides if overrides.is_dir() else None,
        project_dir,
        loaded.context,
    )

    # 5. provenance
    (pkg_dir / "_about.py").write_text(
        _ABOUT.format(
            spec_version=spec_version,
            phantasos_version="0.1.0",
            oag_version=generate.OAG_VERSION,
        ),
        encoding="utf-8",
    )

    # 6. smoke
    result = smoke.smoke(str(project_dir), cfg.package, run=run_smoke)
    return {
        "preprocess": dict(stats),
        "patches": patch_stats,
        "vendored": vendored,
        "smoke": result,
    }


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
