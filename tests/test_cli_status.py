# tests/test_cli_status.py
"""Task 7：``status`` 命令接线。

R2：用 ``tmp_path/bin/uv`` 桩替换真实 ``uv``，避免网络与 uv 依赖。
R4：显式 ``--workdir``，避免触碰真实 ``~/.hermes``。
R6：全局 ``--json`` 必须放在 ``status`` 之前；处理器负责把 ``--json`` 附加到
子进程参数。
"""
import json
import os

from loop_engineering.cli import main


def test_status_uses_quick_status_json(tmp_path, monkeypatch, capsys):
    d = tmp_path / "scripts"; d.mkdir()
    qs = d / "quick_status.py"
    qs.write_text('import json;print(json.dumps({"phase":"IDLE"}))\n')

    # 桩 uv：丢弃 `uv`/`run`/`python` 三个前置 token，把 <script> 及其后参数
    # 原样交给 python3（quick_status.py 无 .sh wrapper，故以 uv run python 调用）。
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/bash\nexec python3 "${@:3}"\n')
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])

    rc = main(["--json", "--scripts", str(d), "--workdir", str(tmp_path), "status"])
    assert rc == 0 and json.loads(capsys.readouterr().out)["phase"] == "IDLE"
