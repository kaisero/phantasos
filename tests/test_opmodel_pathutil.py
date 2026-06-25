"""Unit tests for the on_sys_path context manager."""

from __future__ import annotations

import sys
from pathlib import Path

from phantasos.generator.opmodel._pathutil import on_sys_path


def test_inserts_and_removes_when_absent(tmp_path: Path) -> None:
    p = str(tmp_path)
    assert p not in sys.path
    with on_sys_path(tmp_path):
        assert sys.path[0] == p
    assert p not in sys.path


def test_leaves_preexisting_entry_untouched(tmp_path: Path) -> None:
    p = str(tmp_path)
    sys.path.insert(0, p)
    try:
        with on_sys_path(tmp_path):
            assert p in sys.path
        assert p in sys.path  # we did not insert it, so we must not remove it
    finally:
        sys.path.remove(p)


def test_removes_even_on_exception(tmp_path: Path) -> None:
    p = str(tmp_path)
    try:
        with on_sys_path(tmp_path):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert p not in sys.path
