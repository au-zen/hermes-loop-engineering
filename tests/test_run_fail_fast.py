# tests/test_run_fail_fast.py
"""Task 8：``run`` 的 fail-fast 行为——失败/未知结果必须在下一步启动前停止。

R3（已修正 brief 缺陷）：``test_unknown_result_stops_sequence`` 中标记文件
必须挂在**第二步** ``collector``（触达即证明未停止）；**第一步** ``verify``
（``business_signal=none``）退出 0 归一化为 ``unknown``（退出码 3），必须在
``collector`` 运行前停止序列。

R4（hermeticity）：每个 ``main(...)`` 都显式传 ``--workdir <tmp_path>``。
"""
from loop_engineering.cli import main


def _mk(tmp_path, name, body):
    d = tmp_path / "scripts"; d.mkdir(exist_ok=True)
    w = d / name; w.write_text("#!/bin/bash\n" + body); w.chmod(0o755)


def test_failure_stops_sequence(tmp_path):
    _mk(tmp_path, "cron_loop_collector.sh", f"touch {tmp_path}/ran1; exit 1\n")
    _mk(tmp_path, "loop_auto_verify.sh", f"touch {tmp_path}/ran2; exit 0\n")
    d = tmp_path / "scripts"
    rc = main(["--scripts", str(d), "--db", str(tmp_path / 'x'), "--workdir", str(tmp_path),
               "run", "collector", "verify"])
    assert rc == 1 and (tmp_path / "ran1").exists() and not (tmp_path / "ran2").exists()


def test_unknown_result_stops_sequence(tmp_path):
    # R3：标记放在 collector（第二步）；verify（第一步）返回 unknown → 必须停止。
    _mk(tmp_path, "cron_loop_collector.sh", f"touch {tmp_path}/ran2; exit 0\n")
    _mk(tmp_path, "loop_auto_verify.sh", "exit 0\n")
    d = tmp_path / "scripts"
    rc = main(["--scripts", str(d), "--db", str(tmp_path / 'x'), "--workdir", str(tmp_path),
               "run", "verify", "collector"])
    assert rc == 3 and not (tmp_path / "ran2").exists()
