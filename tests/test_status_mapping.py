import pytest
from loop_engineering.output import Status, parse_loop_status, normalize_status


def test_execution_failure_dominates_regardless_of_sentinel():
    assert normalize_status(1, "ok", "sentinel") == (Status.FAILURE, 1)


def test_exit_code_signal_success_on_zero():
    assert normalize_status(0, None, "exit_code") == (Status.SUCCESS, 0)


def test_none_and_candidate_are_unknown_on_zero():
    assert normalize_status(0, "ok", "none") == (Status.UNKNOWN, 3)
    assert normalize_status(0, "ok", "candidate") == (Status.UNKNOWN, 3)


@pytest.mark.parametrize("sentinel,expected", [
    ("ok", (Status.SUCCESS, 0)),
    ("fallback_ok", (Status.SUCCESS, 0)),
    ("degraded", (Status.DEGRADED, 4)),
    ("failed", (Status.FAILURE, 1)),
    ("skipped", (Status.SKIPPED, 0)),
    ("dry-run", (Status.DRY_RUN, 0)),
    (None, (Status.UNKNOWN, 3)),
    ("weird", (Status.UNKNOWN, 3)),
])
def test_sentinel_signal_mapping(sentinel, expected):
    assert normalize_status(0, sentinel, "sentinel") == expected


def test_parse_takes_last_sentinel():          # Review Focus #4
    out = "LOOP_STATUS: ok\nwork\nLOOP_STATUS: failed\n"
    assert parse_loop_status(out) == "failed"


def test_parse_returns_none_when_absent():
    assert parse_loop_status("no marker here\n") is None
