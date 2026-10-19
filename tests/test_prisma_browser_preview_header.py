"""prisma-browser preview header: the built SDK sends it by default, never as an arg."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest


def _import(real_sdk: Path, name: str):  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(real_sdk))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.remove(str(real_sdk))


def test_preview_header_is_not_an_operation_argument(real_sdk: Path) -> None:
    api = _import(real_sdk, "prisma_browser.api.application_tags_api")
    params = inspect.signature(api.ApplicationTagsApi.list_application_tags).parameters
    assert "x_prisma_browser_preview" not in params


def test_client_sends_preview_header_by_default(real_sdk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISMA_BROWSER_PREVIEW", raising=False)
    pb = _import(real_sdk, "prisma_browser")
    facade = _import(real_sdk, "prisma_browser.extras.facade")
    api_client = pb.ApiClient(pb.Configuration(host="https://example.invalid"))
    facade.Client(api_client)
    assert api_client.default_headers["x-prisma-browser-preview"] == "true"
