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


def test_exit_code_role_treats_failed_sentinel_as_failure():
    # 不把失败伪装成成功：exit_code 角色退出 0，但显式 `failed` 哨兵仍按失败处理。
    assert normalize_status(0, "failed", "exit_code") == (Status.FAILURE, 1)
    # 其余哨兵（含缺失）不影响 exit_code 判定。
    assert normalize_status(0, "ok", "exit_code") == (Status.SUCCESS, 0)
    assert normalize_status(0, None, "exit_code") == (Status.SUCCESS, 0)


def test_parse_skips_vocabulary_enumeration_line():    # issue #1
    # 说明行 `LOOP_STATUS: ok|fallback_ok|degraded|failed` 不是哨兵，必须跳过。
    assert parse_loop_status("LOOP_STATUS: ok|fallback_ok|degraded|failed\n") is None
    # 跳过枚举行后，最后一条真实哨兵仍然生效。
    out = "LOOP_STATUS: ok\nLOOP_STATUS: ok|degraded\n"
    assert parse_loop_status(out) == "ok"
