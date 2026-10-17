import pytest
from loop_engineering.roles import ROLES, get_role, UnknownRoleError

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
