# tests/test_cli_run_role.py
"""Task 7：``main`` 的单角色接线（默认模式 / JSON 模式 / 未知角色 / 退出码）。

R4（hermeticity）：每个 ``main(...)`` 都显式传 ``--workdir <tmp_path>``（外加
``--scripts``/``--db``），确保不解析或触碰真实 ``~/.hermes``。
"""
import json

from loop_engineering.cli import main


def _fake(tmp_path, body):
    d = tmp_path / "scripts"; d.mkdir()
    w = d / "loop_auto_verify.sh"; w.write_text("#!/bin/bash\n" + body); w.chmod(0o755)
    return d


def _argv(tmp_path, d, *extra):
    return ["--scripts", str(d), "--db", str(tmp_path / 'x.duckdb'),
            "--workdir", str(tmp_path), *extra]


def test_role_passthrough_stdout_and_exit(tmp_path, capsys):
    d = _fake(tmp_path, 'echo hello\nexit 0\n')
    rc = main(_argv(tmp_path, d, "verify"))
    # verify 的 business_signal 为 "none"：子进程退出 0 → UNKNOWN → CLI 退出 3
    # （设计 §8.1），同时 stdout 透传。brief 原断言 rc==0 是已知缺陷（已修正）。
    assert rc == 3 and "hello" in capsys.readouterr().out


def test_json_mode_emits_single_parseable_object(tmp_path, capsys):   # Review Focus #3
    d = _fake(tmp_path, 'echo "log line"\necho "LOOP_STATUS: ok"\n')
    rc = main(_argv(tmp_path, d, "--json", "verify"))
    out = capsys.readouterr().out
    obj = json.loads(out)                # 必须整体可解析（子进程日志不得泄漏到 stdout）
    assert obj["role"] == "verify" and "log line" in obj["child_stdout"]


def test_json_mode_still_emits_json_on_failure(tmp_path, capsys):
    d = _fake(tmp_path, 'echo boom\nexit 9\n')
    rc = main(_argv(tmp_path, d, "--json", "verify"))
    obj = json.loads(capsys.readouterr().out)
    assert rc == 9 and obj["status"] == "failure" and obj["child_exit_code"] == 9


def test_unknown_role_exit_2(tmp_path, capsys):
    assert main(["--scripts", str(tmp_path), "--workdir", str(tmp_path), "analyzer"]) == 2


def test_start_error_is_surfaced_on_stderr_in_default_mode(tmp_path, capsys):
    # Fix 2：wrapper 缺失（启动前失败）在默认模式下也必须把 error 打到 stderr，
    # 同时透传退出码 5，且绝不写 stdout。
    rc = main(["--scripts", str(tmp_path), "--workdir", str(tmp_path), "verify"])
    captured = capsys.readouterr()
    assert rc == 5
    assert "error:" in captured.err
    assert captured.out == ""
