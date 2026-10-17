# tests/test_runner.py
import os, pytest
from pathlib import Path
from loop_engineering.config import Config
from loop_engineering.roles import RoleSpec
from loop_engineering.output import Status
from loop_engineering.runner import run_role

def _mk(tmp_path, body, name="w.sh"):
    p = Path(tmp_path) / name
    p.write_text("#!/bin/bash\nset -uo pipefail\n" + body)
    p.chmod(0o755); return p

def _cfg(tmp_path):
    return Config(str(tmp_path), str(tmp_path), str(tmp_path / "x.duckdb"))

COLLECTOR = RoleSpec("collector", "w.sh", "exit_code", True)
SENTINEL  = RoleSpec("synth", "w.sh", "sentinel", True)

def test_exit_zero_is_success_for_exit_code_signal(tmp_path):
    _mk(tmp_path, 'echo hi\nexit 0\n')
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert (r.status, r.exit_code, r.child_exit_code) == (Status.SUCCESS, 0, 0)

def test_nonzero_passthrough(tmp_path):
    _mk(tmp_path, 'echo bad\nexit 7\n')
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert (r.status, r.exit_code, r.child_exit_code) == (Status.FAILURE, 7, 7)

def test_nonzero_code_colliding_with_reserved_passthrough(tmp_path):  # Review Focus #5
    _mk(tmp_path, 'exit 3\n')
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert (r.exit_code, r.status, r.child_exit_code) == (3, Status.FAILURE, 3)

def test_signal_death_maps_to_128_plus_n(tmp_path):                  # Review Focus #2
    _mk(tmp_path, 'kill -TERM $$\n')
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert r.exit_code == 143 and r.status == Status.FAILURE

def test_missing_wrapper_is_start_error_not_crash(tmp_path):         # Review Focus #1
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert r.exit_code == 5 and r.child_exit_code is None
    assert r.status == Status.UNKNOWN and r.error

def test_sentinel_role_parses_last_and_normalizes(tmp_path):
    _mk(tmp_path, 'echo "LOOP_STATUS: ok"\necho "LOOP_STATUS: degraded"\n')
    r = run_role(SENTINEL, [], _cfg(tmp_path))
    assert r.loop_status == "degraded" and r.exit_code == 4

def test_stdout_captured_and_child_args_forwarded(tmp_path):
    _mk(tmp_path, 'echo "ARG:$1"\n')
    r = run_role(COLLECTOR, ["--dry-run"], _cfg(tmp_path))
    assert "ARG:--dry-run" in r.child_stdout

def test_timestamps_are_set(tmp_path):
    _mk(tmp_path, 'exit 0\n')
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert r.started_at and r.finished_at


def test_child_stderr_is_inherited_not_captured(tmp_path, capfd):
    # Fix 1：子进程 stderr 不捕获（stderr=None），诊断必须到达父进程 stderr。
    _mk(tmp_path, 'echo "BOOM" 1>&2\nexit 0\n')
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert r.exit_code == 0
    assert "BOOM" in capfd.readouterr().err


def test_non_utf8_child_output_does_not_become_start_failure(tmp_path):
    # 非 UTF-8 子进程输出必须以 errors="replace" 解码，绝不伪装成启动失败。
    _mk(tmp_path, "printf '\\xff\\xfe\\n'\nexit 0\n")
    r = run_role(COLLECTOR, [], _cfg(tmp_path))
    assert (r.status, r.exit_code) == (Status.SUCCESS, 0)


def test_missing_cwd_is_start_error(tmp_path):
    # cwd 不存在 → OSError → 启动失败（exit 5 / UNKNOWN），不崩栈。
    _mk(tmp_path, "exit 0\n")
    cfg = Config(str(tmp_path / "does-not-exist"), str(tmp_path), str(tmp_path / "x.duckdb"))
    r = run_role(COLLECTOR, [], cfg)
    assert (r.status, r.exit_code, r.child_exit_code) == (Status.UNKNOWN, 5, None)


def test_programming_error_propagates_instead_of_masking(tmp_path, monkeypatch):
    # 非 OSError 的编程错误不得伪装成"wrapper 启动失败"，必须带 traceback 崩出。
    _mk(tmp_path, "exit 0\n")
    import loop_engineering.runner as runner

    def boom(*a, **k):
        raise ValueError("programming bug")

    monkeypatch.setattr(runner.subprocess, "run", boom)
    with pytest.raises(ValueError):
        run_role(COLLECTOR, [], _cfg(tmp_path))
