"""Top-level composing client for the federated `fedsdk` test fixture.

The offline analog of the real built SDK's `prisma_access/__init__.py`: ties the
sub-packages into one SDK and exposes `_SUBPACKAGES` — the introspection registry a
federated CLI/docs enumerate (the analog of a facade's `_WRAPPERS`/`_RESOURCES`).

Unlike the real composer (which builds every sub-facade eagerly in `__init__`), this
`Client` is LAZY: each `.alpha`/`.beta` handle is built on first access via
`cached_property`. `.beta` declares a REQUIRED header sourced from `FEDSDK_REGION`
(mirroring the real composer's `required_for` env-header pattern) and raises a clear
error if it is unset; `.alpha` declares none. Constructing the `Client` therefore
never reads the header — only touching `.beta` does.
"""

from __future__ import annotations

import os
from functools import cached_property
from typing import Any

from .alpha.extras.facade import Client as _AlphaClient
from .beta.extras.facade import Client as _BetaClient

__version__ = "0.0.1"

# slug -> sub-package facade Client (the enumeration seam a federated CLI/docs
# introspect from the built artifact, mirroring _WRAPPERS/_RESOURCES).
_SUBPACKAGES = {
    "alpha": _AlphaClient,
    "beta": _BetaClient,
}
__all__ = ["_SUBPACKAGES", "Client"]


class Client:
    """One SDK over both sub-packages, built lazily (each handle on first access)."""

    def __init__(self, api_client: Any = None) -> None:
        self._api_client = api_client

    @cached_property
    def alpha(self) -> Any:
        return _AlphaClient(self._api_client)

    @cached_property
    def beta(self) -> Any:
        region = os.environ.get("FEDSDK_REGION")  # spec-driven required header
        if region is None:
            raise RuntimeError(
                "fedsdk: required header 'X-Fedsdk-Region' for sub-package 'beta' "
                "is unset; set the FEDSDK_REGION environment variable"
            )
        # a real composer would stamp default_headers['X-Fedsdk-Region'] = region here
        return _BetaClient(self._api_client)
