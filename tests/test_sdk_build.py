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
from phantasos.generator.sdk.build import _about_text, _phantasos_version, build
from phantasos.productconfig import load_product

_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

# The full prisma-access federation (P2.2). `objects` is first = the hoist donor.
_ALL_SLUGS = (
    "objects",
    "network_services",
    "ztna_connector",
    "config_operations",
    "config_setup",
    "deployment_services",
    "device_settings",
    "identity_services",
    "incidents",
    "mobile_agent",
    "posture",
    "security_services",
)


def test_about_uses_real_phantasos_version() -> None:
    """``_about.py`` records the REAL installed phantasos version, not ``0.1.0``.

    The version used to be hardcoded (``phantasos_version="0.1.0"``) — a provenance
    lie that never tracked releases. It now comes from ``importlib.metadata`` (with a
    ``"0+unknown"`` fallback when phantasos is not installed).
    """
    txt = _about_text("1.0", "7.22.0")
    assert "PHANTASOS_VERSION" in txt
    # the old hardcoded literal line is gone:
    assert "PHANTASOS_VERSION = '0.1.0'\n" not in txt
    ver = _phantasos_version()
    assert ver != "0.1.0"  # a real metadata version (e.g. 0.1.0a1) or the fallback
    assert f"PHANTASOS_VERSION = {ver!r}\n" in txt


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
def test_full_federation_twelve_subpackages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Federated build loop emits ALL 12 sub-packages under the distribution root.

    sdk.yml federates the full 12 specs (P2.2). Each one runs the real OAG
    generate (dotted ``--package-name prisma_access.<slug>``) → patches → vendor
    (facade, auth suppressed) loop — so the built tree must carry
    ``prisma_access/<slug>/{__init__.py, api/, models/}`` for every sub, and each
    sub's anchorless None-classified ops are bound/hidden by its per-sub
    ``operations:`` block (the facade vendor raises on an unbound one).

    P1.4 capstone (offline): against the REAL built tree this also proves the
    runtime/auth mechanisms the composer (P2.1) depends on — the libcst hoist
    shape, per-handle ``.models`` namespace resolution, a shared transport pool,
    and that the ``_BearerApiClient`` override attaches the bearer even with empty
    ``auth_settings`` (across subs whose hardcoded schemes diverge).

    P2.2 capstone (offline): the composer ``__init__`` ties all 12 together —
    ``import prisma_access`` exposes ``Client`` + a 12-entry ``_SUBPACKAGES``
    registry, every ``prisma_access.<slug>`` imports cleanly, and constructing
    ``Client(cfg)`` with the stubbed-token config exposes all 12 ``.<slug>``
    facade handles (one config + one pool fanned out, retry landed via the first).
    """
    loaded = load_product("prisma-access")
    # Build into an isolated tmp dir, NOT the shared sibling `prisma-access-sdk/`
    # (load_product's output:). The offline gate and CI run `pytest` bare (no
    # `-m "not slow"`), so this slow federated build runs concurrently with any
    # other gate building the same product — two builds in one output dir race on
    # the hoist's delete-per-sub-runtime step and intermittently leak a per-sub
    # `api_client.py`. A per-run output dir makes the build hermetic.
    loaded.output_dir = tmp_path / "prisma-access-sdk"
    build(loaded, run_smoke=False)
    root = loaded.output_dir / "prisma_access"
    for slug in _ALL_SLUGS:
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

        # 1. Hoist shape: ONE runtime api_client; NO per-sub copies (all 12).
        assert (root / "_runtime" / "api_client.py").exists()
        for slug in _ALL_SLUGS:
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

        # --- P2.2 capstone: every sub imports + the composer fuses all 12 ---
        # Full-12 de-risk: each generated sub-package imports cleanly against the
        # hoisted _runtime (its anchorless ops were bound/hidden, so vendor wrote a
        # real resources.py — an unbound one would have failed the build above).
        for slug in _ALL_SLUGS:
            importlib.import_module(f"prisma_access.{slug}")

        pa = importlib.import_module("prisma_access")  # the composer __init__
        assert hasattr(pa, "Client")
        # _SUBPACKAGES is the rev-7/D10 introspection registry (slug -> facade).
        assert set(pa._SUBPACKAGES) == set(_ALL_SLUGS)
        assert len(pa._SUBPACKAGES) == 12

        # P3.1: incidents declares `X-PANW-Region` as `required_for` it, so the
        # composer's fail-loud fires at construction when PANW_REGION is unset —
        # naming the header, the env var, and the sub-package. prisma-tenant is
        # optional, so its env being unset must NOT raise. (The earlier subs in
        # the loop construct before incidents raises, so this also wires retry
        # onto the shared config — hence the `is None` check precedes it.)
        assert cfg.retries is None  # SdkConfiguration starts with no retry
        monkeypatch.delenv("PANW_REGION", raising=False)
        monkeypatch.delenv("PRISMA_TENANT", raising=False)
        with pytest.raises(RuntimeError) as exc:
            pa.Client(cfg)
        msg = str(exc.value)
        assert "X-PANW-Region" in msg and "PANW_REGION" in msg and "incidents" in msg

        # Construct the real composing Client with the stubbed-token config (no
        # network: the TokenManager above is pre-seeded). One config, one pool,
        # twelve facade handles. PANW_REGION now set -> incidents constructs.
        monkeypatch.setenv("PANW_REGION", "americas")
        client = pa.Client(cfg)
        assert client._configuration is cfg
        # rev-2 B6: the default header lands on the ApiClient HANDLE (what OAG
        # merges into every request), not on Configuration. Applied client-wide.
        assert (
            client.incidents.api_client.default_headers["X-PANW-Region"] == "americas"
        )
        assert client.objects.api_client.default_headers["X-PANW-Region"] == "americas"
        # prisma-tenant env unset -> optional header simply not applied (no raise).
        assert "prisma-tenant" not in client.incidents.api_client.default_headers
        for slug in _ALL_SLUGS:
            assert getattr(client, slug) is not None
        # Each handle resolves its OWN models namespace (no cross-bleed).
        assert client.objects.api_client.models is objects_models
        assert client.ztna_connector.api_client.models is ztna_models
        # The three facades share the ONE connection pool the composer built.
        assert (
            client.objects.api_client.rest_client
            is client.ztna_connector.api_client.rest_client
        )
        # client.objects.<object> is a usable typed wrapper (clean verbs only).
        assert hasattr(client.objects.address, "create")
        assert not hasattr(client.objects.address, "create_address")
        # Retry got wired onto the SHARED config by the first sub-facade's
        # __init__ (the shared _auth.py rendered with has_retry=False, so the
        # composer must not ship a retry-less client).
        assert cfg.retries is not None
    finally:
        sys.path.remove(str(loaded.output_dir))
        _drop()
        sys.modules.update(saved)
