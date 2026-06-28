"""Introspection contract for the federated `fedsdk` test fixture.

`fedsdk` is the offline analog of `fakesdk` for the FEDERATED (multi-spec) CLI
generator: a top-level composing package with two sub-packages (`alpha`, `beta`),
each a real importable mini-SDK with its own `extras/facade._WRAPPERS`/`_RESOURCES`
and typed `_bindings`. These tests pin the contract every later federated task
(merge, dispatch, connection-fields, registry-namespacing) builds on:

- `fedsdk._SUBPACKAGES` enumerates the two subs;
- `cli_operations("fedsdk.<sub>", FIXTURE)` introspects each sub independently;
- the composing `Client` is LAZY — building it never reads the required header,
  but touching `.beta` (which declares one) raises when the env var is unset;
- `alpha.models.Status` and `beta.models.Status` are DISTINCT classes with
  different fields (the model-name collision canary registry-namespacing resolves).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

from phantasos.generator.cli.classify import cli_operations
from phantasos.generator.opmodel._pathutil import on_sys_path

FIXTURE = Path(__file__).parent / "fixtures" / "fedsdk"


def _import(module: str) -> Any:
    with on_sys_path(FIXTURE):
        return importlib.import_module(module)


def _surface(sub: str) -> set[tuple[str | None, str | None]]:
    inv = cli_operations(f"fedsdk.{sub}", FIXTURE)
    return {(op.object_attr, op.clean_method) for op in inv.operations}


def test_subpackages_registry_enumerates_alpha_and_beta() -> None:
    fedsdk = _import("fedsdk")
    assert set(fedsdk._SUBPACKAGES) == {"alpha", "beta"}


def test_alpha_exposes_widget_crud_surface() -> None:
    surface = _surface("alpha")
    objects = {obj for obj, _ in surface}
    assert objects == {"widget"}
    verbs = {verb for _, verb in surface}
    assert {"create", "get", "list", "update", "delete"} <= verbs


def test_beta_exposes_gadget_crud_plus_non_crud_action() -> None:
    surface = _surface("beta")
    objects = {obj for obj, _ in surface}
    assert objects == {"gadget"}
    verbs = {verb for _, verb in surface}
    assert {"create", "get", "list", "update", "delete"} <= verbs
    # the non-CRUD action — a clean verb outside the CRUD set (the collision/
    # dispatch canary for federated classification).
    assert "compute" in verbs


def test_status_models_collide_by_name_but_are_distinct() -> None:
    alpha_status = _import("fedsdk.alpha.models").Status
    beta_status = _import("fedsdk.beta.models").Status
    assert alpha_status is not beta_status
    assert alpha_status.__name__ == beta_status.__name__ == "Status"
    assert set(alpha_status.model_fields) == {"code", "note"}
    assert set(beta_status.model_fields) == {"state", "level"}


def test_client_is_lazy_and_alpha_needs_no_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FEDSDK_REGION", raising=False)
    fedsdk = _import("fedsdk")
    client = fedsdk.Client()  # constructing must NOT read the required header
    assert client.alpha is not None  # alpha declares no required header


def test_beta_requires_region_header_on_first_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fedsdk = _import("fedsdk")

    monkeypatch.delenv("FEDSDK_REGION", raising=False)
    with pytest.raises(RuntimeError, match="FEDSDK_REGION"):
        _ = fedsdk.Client().beta

    monkeypatch.setenv("FEDSDK_REGION", "us")
    assert fedsdk.Client().beta is not None
