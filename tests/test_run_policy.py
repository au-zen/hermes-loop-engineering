# tests/test_run_policy.py
"""Task 8：``run`` 顺序执行的成功/用法错误路径与 §9.2 策略表。

R4（hermeticity）：每个 ``main(...)`` 都显式传 ``--workdir <tmp_path>``
（外加 ``--scripts``/``--db``），确保不解析或触碰真实 ``~/.hermes``。

本文件同时用 ``monkeypatch`` 直接驱动 ``run_sequence``，逐一锁定策略表的每个
``Status`` 分支。
"""
import json

import pytest

from loop_engineering import cli
from loop_engineering.cli import main
from loop_engineering.config import Config
from loop_engineering.output import Result, Status


def _one_role_dir(tmp_path, body):
    d = tmp_path / "scripts"; d.mkdir()
    w = d / "cron_loop_collector.sh"; w.write_text("#!/bin/bash\n" + body); w.chmod(0o755)
    return d


def _argv(tmp_path, d, *extra):
    return ["--scripts", str(d), "--db", str(tmp_path / "x"), "--workdir", str(tmp_path), *extra]


def test_empty_sequence_is_usage_error(tmp_path, capsys):
    assert main(["--scripts", str(tmp_path), "--workdir", str(tmp_path), "run"]) == 2


def test_unknown_role_is_validated_before_any_role_runs(tmp_path, capsys):
    # Fix 3：第二个角色拼写错误时，第一个角色绝不能被先执行（无半执行副作用）。
    d = tmp_path / "scripts"; d.mkdir()
    w = d / "cron_loop_collector.sh"
    w.write_text(f"#!/bin/bash\ntouch {tmp_path}/ran1; exit 0\n")
    w.chmod(0o755)
    rc = main(_argv(tmp_path, d, "run", "collector", "nope_typo"))
    captured = capsys.readouterr()
    assert rc == 2
    assert not (tmp_path / "ran1").exists()
    assert "error:" in captured.err


def test_success_then_success_returns_zero(tmp_path):
    d = _one_role_dir(tmp_path, "exit 0\n")
    assert main(_argv(tmp_path, d, "run", "collector", "collector")) == 0


def test_json_mode_emits_single_run_object(tmp_path, capsys):
    d = _one_role_dir(tmp_path, "exit 0\n")
    rc = main(_argv(tmp_path, d, "--json", "run", "collector", "collector"))
    out = capsys.readouterr().out
    obj = json.loads(out)  # R9：整个 stdout 必须是恰好一个可解析 JSON 对象
    assert rc == 0
    assert obj["command"] == "run"
    assert len(obj["steps"]) == 2
    assert [s["role"] for s in obj["steps"]] == ["collector", "collector"]


# --- 直接驱动 run_sequence 的策略表测试（无需真实子进程）----------------------


def _cfg(tmp_path) -> Config:
    return Config(
        workdir=str(tmp_path),
        scripts_dir=str(tmp_path / "scripts"),
        db_path=str(tmp_path / "x"),
    )


def _res(role: str, status: Status, exit_code: int) -> Result:
    return Result(
        role=role,
        status=status,
        child_exit_code=0,
        exit_code=exit_code,
        loop_status=None,
        started_at="t0",
        finished_at="t1",
        error=None,
        wrapper_path=None,
        child_stdout=None,
    )


def _patch_run_role(monkeypatch, results):
    """用脚本化结果替换 ``run_role``，返回记录被调用角色名的列表。"""
    calls: list[str] = []

    def fake(spec, child_args, cfg):
        calls.append(spec.name)
        return results[len(calls) - 1]

    monkeypatch.setattr(cli, "run_role", fake)
    return calls


def test_run_sequence_empty_raises_usage_error(tmp_path):
    with pytest.raises(cli.UsageError):
        cli.run_sequence([], _cfg(tmp_path), False, False)


def test_degraded_stops_by_default(monkeypatch, tmp_path):
    calls = _patch_run_role(
        monkeypatch,
        [_res("collector", Status.DEGRADED, 4), _res("collector", Status.SUCCESS, 0)],
    )
    rc = cli.run_sequence(["collector", "collector"], _cfg(tmp_path), False, False)
    assert rc == 4 and len(calls) == 1


def test_degraded_continues_with_flag(monkeypatch, tmp_path):
    calls = _patch_run_role(
        monkeypatch,
        [_res("collector", Status.DEGRADED, 4), _res("collector", Status.SUCCESS, 0)],
    )
    rc = cli.run_sequence(["collector", "collector"], _cfg(tmp_path), False, True)
    assert rc == 0 and len(calls) == 2


def test_run_default_mode_writes_error_to_stderr(monkeypatch, tmp_path, capsys):
    # issue #2：run 默认模式必须把 result.error 落到 stderr（否则失败无可读原因）。
    def fake(spec, child_args, cfg):
        return Result(
            role=spec.name,
            status=Status.UNKNOWN,
            child_exit_code=None,
            exit_code=5,
            loop_status=None,
            started_at="t0",
            finished_at="t1",
            error="无法启动 wrapper：/nope.sh",
            wrapper_path="/nope.sh",
            child_stdout="",
        )

    monkeypatch.setattr(cli, "run_role", fake)
    rc = cli.run_sequence(["collector"], _cfg(tmp_path), False, False)
    captured = capsys.readouterr()
    assert rc == 5
    assert "error:" in captured.err
    assert "无法启动 wrapper" in captured.err


def test_unknown_stops_and_returns_step_exit_code(monkeypatch, tmp_path):
    calls = _patch_run_role(
        monkeypatch,
        [_res("collector", Status.UNKNOWN, 3), _res("collector", Status.SUCCESS, 0)],
    )
    rc = cli.run_sequence(["collector", "collector"], _cfg(tmp_path), False, False)
    assert rc == 3 and len(calls) == 1
