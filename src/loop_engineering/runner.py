"""单角色执行器：校验 → 启动 wrapper → 归一化结果（设计 §8.1 / §9）。

本模块把 Task 2~5 的三块能力串成一次原子执行：

* :func:`~loop_engineering.config.preflight` 在启动前校验 wrapper；
* :func:`subprocess.run` 以参数数组方式启动子进程（**不经 shell**）；
* :func:`~loop_engineering.output.normalize_status` 把退出码、哨兵、业务信号
  归一化成 (:class:`~loop_engineering.output.Status`, CLI 退出码)。

关键不变量：

* 子进程被信号杀死（``returncode < 0``）时映射为 ``128 + N``，**绝不**把负数
  作为进程退出码返回。
* 启动前失败（:class:`~loop_engineering.config.StartError`）与启动期 ``OSError``
  （cwd 缺失 / 权限等）都归为 ``exit_code=5`` / ``status=UNKNOWN``，永不崩栈；
  其余编程错误**不**吞掉，直接带 traceback 抛出。
* 子进程输出以 ``errors="replace"`` 解码，非 UTF-8 字节不会变成启动失败。
* v1 **不设超时**。
"""

from __future__ import annotations

import subprocess
from datetime import datetime

from .config import Config, StartError, child_env, preflight
from .output import Result, Status, normalize_status, parse_loop_status
from .roles import RoleSpec

#: 启动前失败 / 运行期异常时使用的 CLI 退出码。
EXIT_START_ERROR = 5


def _now() -> str:
    """返回带时区的 ISO-8601 时间戳（本地时钟）。"""
    return datetime.now().astimezone().isoformat()


def _failure_result(
    spec: RoleSpec,
    message: str,
    wrapper: str | None,
) -> Result:
    """构造「未产生有效子进程结果」的失败 :class:`Result`。

    用于启动前失败（wrapper 缺失/不可执行）以及启动期 ``OSError``：
    ``status=UNKNOWN`` / ``child_exit_code=None`` / ``exit_code=5``。
    """
    ts = _now()
    return Result(
        role=spec.name,
        status=Status.UNKNOWN,
        child_exit_code=None,
        exit_code=EXIT_START_ERROR,
        loop_status=None,
        started_at=ts,
        finished_at=ts,
        error=message,
        wrapper_path=wrapper,
        child_stdout=None,
    )


def run_role(spec: RoleSpec, child_args: list[str], cfg: Config) -> Result:
    """执行单个角色的 wrapper 并返回归一化 :class:`Result`。

    :param spec: 待执行角色的固定注册项。
    :param child_args: 透传给 wrapper 的**额外参数**（仅 ``--`` 之后的 token；
        分隔符本身不在内）。
    :param cfg: 解析后的运行配置。
    :return: 一次执行的完整结果；失败也以 :class:`Result` 返回，绝不抛异常。
    """
    # 1. 启动前校验：失败立即返回，不启动子进程。
    try:
        wrapper = preflight(spec, cfg)
    except StartError as exc:
        return _failure_result(spec, str(exc), None)

    started_at = _now()

    # 2/3. 以参数数组启动子进程：仅捕获 stdout，stderr 继承父进程
    # （子进程诊断直接落到 CLI 的 stderr；--json 的 stdout 保持纯净）。
    try:
        completed = subprocess.run(
            [wrapper, *child_args],
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            errors="replace",  # 非 UTF-8 输出按替换字符解码，绝不伪装成启动失败
            env=child_env(cfg),
            cwd=cfg.workdir,
        )
    except OSError as exc:
        # 仅启动期 OSError（cwd 缺失 / 权限等）归一化为启动失败；编程错误照常抛出。
        return _failure_result(spec, f"wrapper 启动失败：{exc}", wrapper)

    finished_at = _now()
    stdout = completed.stdout or ""
    returncode = completed.returncode

    # 4. 信号死亡：映射为 128 + N，绝不透传负数。
    if returncode < 0:
        child_exit_code = 128 + (-returncode)
        status, exit_code = Status.FAILURE, child_exit_code
        loop_status = None
    # 5. 正常退出：从 stdout 解析哨兵原始值并归一化。
    else:
        child_exit_code = returncode
        loop_status = parse_loop_status(stdout)
        status, exit_code = normalize_status(
            returncode, loop_status, spec.business_signal
        )

    return Result(
        role=spec.name,
        status=status,
        child_exit_code=child_exit_code,
        exit_code=exit_code,
        loop_status=loop_status,
        started_at=started_at,
        finished_at=finished_at,
        error=None,
        wrapper_path=wrapper,
        child_stdout=stdout,
    )
