"""Shared introspection primitive: temporarily put a built SDK on sys.path."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def on_sys_path(path: Path) -> Iterator[None]:
    """Insert ``str(path)`` at the front of ``sys.path`` for the block's duration.

    No-op if the entry is already present (and then it is NOT removed on exit),
    so nested/overlapping uses never strip an entry a caller put there.
    """
    entry = str(path)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    try:
        yield
    finally:
        if added and entry in sys.path:
            sys.path.remove(entry)
