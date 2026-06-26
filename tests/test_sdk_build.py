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

    P1.4 capstone (offline): against the REAL built tree this also proves the
    runtime/auth mechanisms the composer (P2.1) will depend on — the libcst hoist
    shape, per-handle ``.models`` namespace resolution, a shared transport pool,
    and that the ``_BearerApiClient`` override attaches the bearer even with empty
    ``auth_settings`` (across subs whose hardcoded schemes diverge).
    """
    loaded = load_product("prisma-access")
    build(loaded, run_smoke=False)
    root = loaded.output_dir / "prisma_access"
    for slug in ("objects", "network_services", "ztna_connector"):
        assert (root / slug / "__init__.py").exists()
        assert (root / slug / "api").is_dir()
        assert (root / slug / "models").is_dir()

    # P1.3: build() also rendered the ONE shared _auth.py at the package root.
    assert (root / "_auth.py").exists()

    # De-risk: the real built tree imports cleanly — _auth.py imports the hoisted
    # _runtime absolutely, and _BearerApiClient is a subclass of the runtime
    # ApiClient (so update_params_for_auth overrides the right base). Isolate from
    # any real prisma_access an earlier test left in sys.modules.
    import importlib
    import sys
    from types import ModuleType

    def _drop() -> dict[str, ModuleType]:
        return {
            m: sys.modules.pop(m)
            for m in list(sys.modules)
            if m == "prisma_access" or m.startswith("prisma_access.")
        }

    saved = _drop()
    sys.path.insert(0, str(loaded.output_dir))
    try:
        importlib.invalidate_caches()
        auth = importlib.import_module("prisma_access._auth")
        runtime_ac = importlib.import_module("prisma_access._runtime.api_client")
        assert issubclass(auth._BearerApiClient, runtime_ac.ApiClient)
        assert hasattr(auth, "configuration_from_env")
        assert hasattr(auth, "configuration_from_credentials")

        # --- P1.4 capstone: prove the runtime/auth mechanisms before P2.1 ---

        # 1. Hoist shape: ONE runtime api_client; NO per-sub copies.
        assert (root / "_runtime" / "api_client.py").exists()
        for slug in ("objects", "network_services", "ztna_connector"):
            assert not (root / slug / "api_client.py").exists(), (
                f"per-sub api_client leaked for {slug}"
            )

        # Build a config whose token never touches the network: pre-seed the
        # TokenManager cache so `.token()` returns FAKETOKEN without a fetch.
        import time as _time

        tm = auth.TokenManager("id", "secret", "scope")
        tm._token = "FAKETOKEN"
        tm._expires_at = _time.time() + 3600
        cfg = auth.SdkConfiguration(token_manager=tm)

        objects_models = importlib.import_module("prisma_access.objects.models")
        ztna_models = importlib.import_module("prisma_access.ztna_connector.models")

        # 2. Per-handle `.models` resolves its OWN namespace via the SAME dynamic
        #    `getattr(self.models, <runtime str>)` the hoisted deserialize path uses
        #    (rev-2 B1: `.models` is an instance attr). The class name is held in a
        #    variable on purpose — that is exactly how api_client resolves `klass`.
        ac_obj = auth._BearerApiClient(cfg)
        ac_obj.models = objects_models
        obj_klass = "Addresses"
        assert getattr(ac_obj.models, obj_klass) is objects_models.Addresses

        ac_ztna = auth._BearerApiClient(cfg)
        ac_ztna.models = ztna_models
        ztna_klass = "ConnectorNew"
        assert getattr(ac_ztna.models, ztna_klass) is ztna_models.ConnectorNew

        # Each handle sees only its own models — no cross-namespace bleed.
        assert not hasattr(ac_obj.models, "ConnectorNew")
        assert not hasattr(ac_ztna.models, "Addresses")

        # 3. Shared transport pool: what the composer will wire (one RESTClientObject
        #    fanned out to every handle).
        rest_mod = importlib.import_module("prisma_access._runtime.rest")
        pool = rest_mod.RESTClientObject(cfg)
        ac_obj.rest_client = pool
        ac_ztna.rest_client = pool
        assert ac_obj.rest_client is ac_ztna.rest_client

        # 4. Bearer attaches at the transport layer even with EMPTY auth_settings
        #    (posture's no-scheme case) — proving the override ignores per-op
        #    `_auth_settings` and is what unifies auth across divergent specs.
        headers: dict[str, str] = {}
        ac_obj.update_params_for_auth(
            headers=headers,
            queries=[],
            auth_settings=[],
            resource_path="/x",
            method="GET",
            body=None,
        )
        assert headers["Authorization"] == "Bearer FAKETOKEN", headers

        # 5. The generated subs carry DIVERGENT hardcoded `_auth_settings` (objects
        #    => scmToken, ztna => bearerAuth) — documenting that the transport hook
        #    above (which ignores them) is what unifies auth.
        obj_api = (root / "objects" / "api" / "addresses_api.py").read_text()
        ztna_api = (root / "ztna_connector" / "api" / "connector_api.py").read_text()
        assert "scmToken" in obj_api and "scmToken" not in ztna_api
        assert "bearerAuth" in ztna_api and "bearerAuth" not in obj_api
    finally:
        sys.path.remove(str(loaded.output_dir))
        _drop()
        sys.modules.update(saved)
