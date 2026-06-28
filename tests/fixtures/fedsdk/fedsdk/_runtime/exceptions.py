"""Shared runtime exceptions for the federated `fedsdk` fixture.

The offline analog of the real built SDK's `prisma_access/_runtime/exceptions.py`:
a federated distribution has NO top-level `exceptions` module — the base lives
under `_runtime`. The federation-aware runtime's `_sdk_exc` resolves here per-sub.
"""

from __future__ import annotations


class OpenApiException(Exception):  # noqa: N818
    """Base exception for all SDK errors (mirrors OAG's `OpenApiException`)."""
