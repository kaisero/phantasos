"""Integration test: full SDK build() emits object wrappers and passes smoke.

Requires the sibling ``../prisma-browser-sdk`` to have been built at least once
(i.e. the output directory exists and the SDK is importable). When present the
test re-runs the full pipeline — preprocess → OAG → patches → vendor (pass1 →
introspect → wrapper-gen → resources.py → pass2) → smoke — and asserts that:

* ``extras/resources.py`` is written to the output package, and
* the smoke import-walk records **zero** failures.

Skipped automatically in CI (where the SDK output directory is absent) and in
any environment without Java/OAG available (the ``build()`` call would fail
before the assertion).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from phantasos.generator.sdk import generate, provision
from phantasos.generator.sdk.build import build
from phantasos.productconfig import load_product

_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"


def _oag_toolchain_cached() -> bool:
    """True only if the OAG jar *and* a usable java are already on disk.

    Mirrors the no-download branches of ``generate.ensure_jar`` and
    ``provision.resolve_java`` so the offline gate (bare ``pytest -q`` — no
    ``-m 'not slow'``) and CI *skip* the federated build rather than triggering a
    one-time ~30 MB jar / ~40 MB JRE download on a cold cache or offline runner.
    """
    # ponytail: replicates resolve_java's cache-path build (can't reuse it — it
    # downloads as a side effect, and the predicate must not touch the network).
    jar = provision.cache_dir() / f"openapi-generator-cli-{generate.OAG_VERSION}.jar"
    if not jar.exists():
        return False
    override = os.environ.get("PHANTASOS_JAVA")
    if override:
        return Path(override).exists()
    try:
        key = provision._platform_key()
    except provision.ProvisionError:
        return False
    java = (
        provision.cache_dir()
        / f"temurin-{provision._JRE_RELEASE}-{key}"
        / provision._JRE[key].java_subpath
    )
    return java.exists()


@pytest.mark.slow
@pytest.mark.skipif(not _SDK.exists(), reason="prisma-browser SDK not built")
def test_build_emits_wrapper() -> None:
    """build() runs the full pass1 → introspect → wrapper-gen → pass2 pipeline.

    Verifies that the vendor step produces ``extras/resources.py`` (typed object
    wrappers) and that the smoke import-walk reports no failures.
    """
    loaded = load_product("prisma-browser")
    res = build(loaded, run_smoke=True)

    # Smoke: every generated module must import cleanly.
    assert res["smoke"]["failed"] == 0, (
        f"Smoke import failures: {res['smoke']['failures']}"
    )

    # resources.py must exist in the output package's extras/ directory.
    # Use loaded.output_dir (resolves relative to the product's base_dir).
    resources_py = loaded.output_dir / loaded.config.package / "extras" / "resources.py"
    assert resources_py.exists(), f"extras/resources.py not found at {resources_py}"


@pytest.mark.slow
@pytest.mark.skipif(
    not Path("products/prisma-access/openapi/objects.yaml").exists(),
    reason="prisma-access specs absent",
)
@pytest.mark.skipif(
    not _oag_toolchain_cached(),
    reason="OAG toolchain not provisioned (offline/CI)",
)
def test_first_light_three_subpackages(tmp_path: Path) -> None:
    """Federated build loop emits each sub-package under the distribution root.

    sdk.yml is limited to 3 sub-packages for P1 first light. Each one runs the
    real OAG generate (dotted ``--package-name prisma_access.<slug>``) →
    patches → vendor (facade, auth suppressed) loop, so the built tree must
    carry ``prisma_access/<slug>/{__init__.py, api/, models/}`` for every sub.
    """
    loaded = load_product("prisma-access")
    build(loaded, run_smoke=False)
    root = loaded.output_dir / "prisma_access"
    for slug in ("objects", "network_services", "ztna_connector"):
        assert (root / slug / "__init__.py").exists()
        assert (root / slug / "api").is_dir()
        assert (root / slug / "models").is_dir()
