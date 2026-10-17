"""测试 pyproject.toml 中的 CLI 入口存在。

这个测试确保 [project.scripts] 不会被意外移除。
如果本机有旧的 uv tool install 残留，这个测试会失败。
"""

import subprocess
import sys
from pathlib import Path

import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cli_entry_exists():
    """pyproject.toml 必须声明 [project.scripts] hermes-loop。"""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert "hermes-loop" in scripts, (
        "pyproject.toml 缺少 [project.scripts] hermes-loop。"
        "如果移除，wrapper 和 README 都会失效。"
    )
    assert scripts["hermes-loop"] == "loop_engineering.cli:main"


def test_install_in_fresh_venv(tmp_path):
    """在临时 venv 里安装包，验证 hermes-loop 命令可用。

    模拟全新 clone 后的安装流程，不依赖本机环境。
    """
    import os
    import shutil

    uv = shutil.which("uv")
    if uv is None:
        import pytest
        pytest.skip("uv not available")

    # 创建临时 venv
    venv_dir = tmp_path / "test_venv"
    subprocess.run(
        [uv, "venv", str(venv_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    # 安装包
    subprocess.run(
        [uv, "pip", "install", "--python", str(venv_dir / "bin" / "python"), str(PROJECT_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )

    # 验证 hermes-loop 命令存在，且不触碰生产：
    # 无参数即用法错误（退出码 2），只证明入口可运行，不触发 status / 生产 DuckDB。
    result = subprocess.run(
        [str(venv_dir / "bin" / "hermes-loop")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, (
        f"hermes-loop 无参数应返回用法错误 2，实际 {result.returncode}: {result.stderr}"
    )
    assert "usage: hermes-loop" in result.stderr
