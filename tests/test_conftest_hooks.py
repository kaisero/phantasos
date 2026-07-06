"""Unit tests for the pytest_terminal_summary ring-3 staleness banner."""

from __future__ import annotations

from conftest import _STALE_SENTINEL, _ring3_stale_summary, _stale_reason_text


def test_banner_fires_on_staleness_skip() -> None:
    # Feed the REAL reason string (the same pure builder _stale_sdk_reason uses),
    # NOT a hand-copied literal — so a reword of the reason is caught here.
    reason = "Skipped: " + _stale_reason_text("abcd1234", "ef567890")
    line = _ring3_stale_summary([reason])
    assert line is not None
    assert line.startswith("⚠ ring-3 OFF:")
    assert "abcd1234" in line and "ef567890" in line  # built + HEAD shas
    assert "nox -s smoke" in line  # rebuild hint
    assert "Skipped:" not in line  # prefix stripped


def test_banner_quiet_when_sdk_absent_not_stale() -> None:
    # the "absent" skip reason must NOT trigger the loud line
    assert (
        _ring3_stale_summary(
            ["Skipped: prisma-browser-sdk not built (run: nox -s smoke)"]
        )
        is None
    )


def test_banner_quiet_when_no_skips() -> None:
    assert _ring3_stale_summary([]) is None


def test_sentinel_is_a_substring_of_the_real_reason() -> None:
    # Drift guard that is NOT a tautology: the reason is BUILT from the sentinel,
    # so this can only pass while _ring3_stale_summary's match key really appears
    # in the text _stale_sdk_reason emits. Reword the reason without the sentinel
    # and BOTH this and test_banner_fires_on_staleness_skip go red.
    assert _stale_reason_text("x", "y").startswith(_STALE_SENTINEL + ":")
