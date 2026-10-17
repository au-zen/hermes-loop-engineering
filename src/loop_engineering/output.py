"""状态模型：把「进程是否成功」与「业务状态是否已知」分开（设计 §8.1）。

核心职责：

* :func:`parse_loop_status` —— 从子进程 stdout 里提取最后一条
  ``LOOP_STATUS`` 哨兵（原样返回，不做归一化）。
* :func:`normalize_status` —— 把子进程退出码、哨兵、以及角色的业务信号来源
  三者归一化成 (:class:`Status`, CLI 退出码)。

设计要点（§8.1）：

* 子进程非零退出即 **执行失败**，优先于一切业务信号，CLI 退出码透传该非零码。
* 退出码 0 时，只有声明为 ``exit_code`` 的角色才可直接视为 ``success``；
  ``none`` / ``candidate`` 角色即 ``unknown``（绝不信任哨兵）。
* 仅 ``sentinel`` 角色才依据哨兵映射；未知或缺失哨兵 → ``unknown``（退出码 3）。
"""

from __future__ import annotations

import re
from enum import Enum

#: CLI 退出码：业务状态未知时使用。
EXIT_UNKNOWN = 3
#: CLI 退出码：业务状态降级时使用。
EXIT_DEGRADED = 4

#: 匹配一条 ``LOOP_STATUS:`` 哨兵行；捕获值为哨兵原始文本（``[\w-]+``）。
_LOOP_STATUS_RE = re.compile(r"^LOOP_STATUS:\s*([\w-]+)", re.M)


class Status(str, Enum):
    """归一化业务状态（设计 §8.1）。继承 ``str`` 便于直接序列化/比较。"""

    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILURE = "failure"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


#: 哨兵 → (状态, CLI 退出码)；未列出者一律 ``unknown``。
_SENTINEL_MAP: dict[str, tuple[Status, int]] = {
    "ok": (Status.SUCCESS, 0),
    "fallback_ok": (Status.SUCCESS, 0),
    "degraded": (Status.DEGRADED, EXIT_DEGRADED),
    "failed": (Status.FAILURE, 1),
    "skipped": (Status.SKIPPED, 0),
    "dry-run": (Status.DRY_RUN, 0),
}


def parse_loop_status(stdout: str) -> str | None:
    """返回 ``stdout`` 中 **最后一条** ``LOOP_STATUS`` 哨兵的原始值。

    末条生效与既有 ``底层 reader`` 的 ``vals[-1]`` 行为一致。
    无匹配时返回 ``None``。

    :param stdout: 子进程标准输出。
    :return: 哨兵原始文本（如 ``"dry-run"``），或 ``None``。
    """
    matches = _LOOP_STATUS_RE.findall(stdout)
    return matches[-1] if matches else None


def normalize_status(
    child_exit_code: int,
    loop_status: str | None,
    business_signal: str,
) -> tuple[Status, int]:
    """把执行结果归一化成 (:class:`Status`, CLI 退出码)（设计 §8.1）。

    :param child_exit_code: 子进程真实退出码。
    :param loop_status: :func:`parse_loop_status` 得到的哨兵原始值（可 ``None``）。
    :param business_signal: 角色的业务信号来源，∈ ``exit_code``/``sentinel``/
        ``none``/``candidate``。
    :return: 二元组 ``(status, cli_exit_code)``。
    """
    # 执行失败优先于一切业务信号；CLI 退出码透传子进程非零码。
    if child_exit_code != 0:
        return (Status.FAILURE, child_exit_code)

    # 子进程成功（退出码 0），按角色的业务信号来源分支。
    if business_signal == "exit_code":
        return (Status.SUCCESS, 0)
    if business_signal in ("none", "candidate"):
        return (Status.UNKNOWN, EXIT_UNKNOWN)
    if business_signal == "sentinel":
        return _SENTINEL_MAP.get(loop_status or "", (Status.UNKNOWN, EXIT_UNKNOWN))
    # 未知 business_signal：保守视为未知。
    return (Status.UNKNOWN, EXIT_UNKNOWN)
