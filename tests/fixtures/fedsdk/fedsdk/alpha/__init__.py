"""`alpha` sub-package.

Re-exports a trivial credential-free `Configuration`/`ApiClient` (the real
`prisma_access.<sub>` re-exports these from `_runtime`), so the federation-aware
runtime can build a credential-free sub client for the `--dry-run` serialize seam.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.0.1"


class Configuration:
    """No-arg-constructible config (mirrors OAG's credential-free `Configuration()`)."""

    def __init__(self) -> None:
        self.host = "https://fedsdk.test"
        self.retries: Any = None


class ApiClient:
    """Minimal api_client carrying its configuration (the dry-run seam needs no I/O)."""

    def __init__(self, configuration: Any = None) -> None:
        self.configuration = configuration or Configuration()
