"""phantasos — generate native, self-contained Python SDKs from OpenAPI specs.

Public API: `build(config, preprocess_hook=None, patch_hook=None)`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
)

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


def build(
    config: Any,
    *,
    preprocess_hook: Callable[[Any], None] | None = None,
    patch_hook: Callable[[Path], None] | None = None,
    run_smoke: bool = True,
) -> dict[str, Any]:
    from . import generate, preprocess, render, smoke

    project_dir = Path(config.project_dir)
    stats: defaultdict[str, int] = defaultdict(int)

    # 1. preprocess (generic transforms + optional spec hook)
    spec, yaml = preprocess.load(config.spec)
    preprocess.clean(spec, stats)
    if preprocess_hook:
        preprocess_hook(spec)
    pp_dir = project_dir / ".phantasos"
    pp_dir.mkdir(parents=True, exist_ok=True)
    pp_path = pp_dir / "preprocessed.yaml"
    preprocess.dump(spec, yaml, str(pp_path))
    spec_version = spec.get("info", {}).get("version")

    # 2. generate
    generate.generate(
        str(pp_path), str(project_dir), config.package, library=config.library
    )
    pkg_dir = project_dir / config.package

    # 3. patches (generic + optional spec hook)
    patch_stats: dict[str, int] = {}
    if config.apply_generic_patches:
        from . import patches

        patch_stats = patches.apply_generic_patches(pkg_dir)
    if patch_hook:
        patch_hook(pkg_dir)

    # 4. vendor components
    vendored = render.vendor(pkg_dir, config)

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
    result = smoke.smoke(str(project_dir), config.package, run=run_smoke)
    return {
        "preprocess": dict(stats),
        "patches": patch_stats,
        "vendored": vendored,
        "smoke": result,
    }
