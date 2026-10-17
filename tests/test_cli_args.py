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


# --- 不静默原则：以下用法一律报错，绝不吞掉参数后返回成功 -------------------


def test_role_rejects_extra_positional_tokens():
    # 每个角色命令用法为 `<role> [-- <args>]`；`--` 之前第二个位置参数是用法错误。
    with pytest.raises(UsageError):
        parse_args(["verify", "extra"])
    assert main(["verify", "extra"]) == 2


def test_status_rejects_extra_positional_tokens():
    # status 不接受任何位置参数（更不支持 `--` 透传）。
    with pytest.raises(UsageError):
        parse_args(["status", "extra"])
    assert main(["status", "extra"]) == 2


def test_run_rejects_double_dash_child_args():
    # `run` 不转发 `--`：同一串参数发给多个角色语义不明，宁可报错也不静默丢弃。
    with pytest.raises(UsageError):
        parse_args(["run", "collector", "--", "--flag"])


def test_value_option_rejects_value_starting_with_dash():
    # `--scripts --json` 曾把 "--json" 吞成取值；现在必须报用法错误。
    with pytest.raises(UsageError):
        parse_args(["--scripts", "--json", "verify"])


def test_value_option_equals_form_is_accepted():
    # `--opt=value` 是取值以 `-` 开头时唯一的合法写法。
    p = parse_args(["--scripts=/s", "--workdir=/w", "--db=/d", "verify"])
    assert (p.scripts, p.workdir, p.db) == ("/s", "/w", "/d")
    assert p.command == "role" and p.roles == ["verify"]
