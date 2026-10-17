import pytest
from loop_engineering.roles import (
    BUSINESS_SIGNALS,
    ROLES,
    RoleSpec,
    get_role,
    UnknownRoleError,
)

#: 全部 10 个角色 → wrapper 文件名的精确映射（逐项锁死，防止动态拼接回归）。
EXPECTED_WRAPPERS = {
    "collector": "cron_loop_collector.sh",
    "log_scanner": "loop_hermes_log_scanner.sh",
    "canary": "loop_canary_injector.sh",
    "verify": "loop_auto_verify.sh",
    "fixer": "loop_auto_fixer.sh",
    "decide": "loop_auto_decide.sh",
    "learn": "loop_learn.sh",
    "notify": "_loop_notify.sh",
    "trust_audit": "loop_trust_audit.sh",
    "daily_diagnostic": "_cron_loop_diag.sh",
}


def test_all_role_wrappers_match_expected_table():
    assert {n: r.wrapper for n, r in ROLES.items()} == EXPECTED_WRAPPERS


def test_registry_is_self_consistent():
    for name, spec in ROLES.items():
        assert spec.name == name
        assert spec.business_signal in BUSINESS_SIGNALS

def test_registry_has_exactly_ten_roles():
    assert set(ROLES) == {
        "collector","log_scanner","canary","verify","fixer",
        "decide","learn","notify","trust_audit","daily_diagnostic",
    }

def test_collector_is_exit_code_signal_and_run_eligible():
    r = ROLES["collector"]
    assert r.wrapper == "cron_loop_collector.sh"
    assert r.business_signal == "exit_code" and r.run_eligible is True

def test_only_collector_is_run_eligible():
    assert [n for n, r in ROLES.items() if r.run_eligible] == ["collector"]

def test_fixer_and_trust_audit_are_candidate():
    assert ROLES["fixer"].business_signal == "candidate"
    assert ROLES["trust_audit"].business_signal == "candidate"

def test_remaining_roles_have_no_signal():
    for n in ["log_scanner","canary","verify","decide","learn","notify","daily_diagnostic"]:
        assert ROLES[n].business_signal == "none"

def test_daily_diagnostic_wrapper_is_the_diag_wrapper():
    assert ROLES["daily_diagnostic"].wrapper == "_cron_loop_diag.sh"

def test_unknown_role_raises():
    with pytest.raises(UnknownRoleError):
        get_role("analyzer")  # 纯 Agent 角色，不在白名单


def test_invalid_business_signal_is_rejected_at_construction():
    # BUSINESS_SIGNALS 不再是"仅供测试引用"的常量：构造期即强制校验。
    with pytest.raises(ValueError):
        RoleSpec("x", "w.sh", "bogus", False)
