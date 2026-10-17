import pytest
from loop_engineering.cli import main, parse_args, UsageError

def test_globals_before_role():
    p = parse_args(["--json", "--workdir", "/w", "verify"])
    assert p.json is True and p.workdir == "/w"
    assert p.command == "role" and p.roles == ["verify"] and p.child_args == []

def test_double_dash_splits_child_args():
    p = parse_args(["trust_audit", "--", "--json", "--days", "7"])
    assert p.command == "role" and p.roles == ["trust_audit"]
    assert p.child_args == ["--json", "--days", "7"]

def test_run_collects_roles():
    p = parse_args(["run", "collector", "verify"])
    assert p.command == "run" and p.roles == ["collector", "verify"]

def test_status_command():
    assert parse_args(["status"]).command == "status"

def test_unknown_global_flag_is_usage_error():
    with pytest.raises(UsageError):
        parse_args(["--nope", "verify"])

def test_global_flag_after_role_is_usage_error():
    # §7.1: 全局选项必须在 <role> 之前
    with pytest.raises(UsageError):
        parse_args(["verify", "--json"])

def test_empty_argv_is_usage_error():
    with pytest.raises(UsageError):
        parse_args([])

def test_globals_only_is_usage_error():
    with pytest.raises(UsageError):
        parse_args(["--json"])
    with pytest.raises(UsageError):
        parse_args(["--workdir", "/w"])


def test_main_usage_error_returns_2_and_logs_stderr(capsys):
    # Fix 8：main() 的用法错误契约——退出码 2 且 stderr 出现 `error:` 行。
    rc = main(["--nope"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "error:" in captured.err
    assert captured.out == ""
