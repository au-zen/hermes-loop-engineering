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
from dataclasses import dataclass
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


#: 哨兵 → (状态, CLI 退出码)；未列出者一律 ``unknown``。
#: 权威词表为 4 值 ``ok|fallback_ok|degraded|failed``（与 reader 对齐）。
#: v1 无 ``sentinel`` 角色，故本表当前不可达；待首个 sentinel 角色出现时再定稿。
_SENTINEL_MAP: dict[str, tuple[Status, int]] = {
    "ok": (Status.SUCCESS, 0),
    "fallback_ok": (Status.SUCCESS, 0),
    "degraded": (Status.DEGRADED, EXIT_DEGRADED),
    "failed": (Status.FAILURE, 1),
}


def parse_loop_status(stdout: str) -> str | None:
    """返回 ``stdout`` 中 **最后一条** ``LOOP_STATUS`` 哨兵的原始值。

    末条生效与既有底层 reader 的 ``vals[-1]`` 行为一致。
    词表说明行（取值后含 ``|``，如 ``LOOP_STATUS: ok|fallback_ok|degraded``）
    不是真实哨兵，予以跳过（issue #1）。无匹配时返回 ``None``。

    :param stdout: 子进程标准输出。
    :return: 哨兵原始文本（如 ``"degraded"``），或 ``None``。
    """
    last: str | None = None
    for match in _LOOP_STATUS_RE.finditer(stdout):
        line_end = stdout.find("\n", match.end())
        if line_end == -1:
            line_end = len(stdout)
        if "|" in stdout[match.end() : line_end]:
            continue
        last = match.group(1)
    return last


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
        # 不把失败伪装成成功：即使退出码为 0，显式 `failed` 哨兵也按失败处理。
        if loop_status == "failed":
            return (Status.FAILURE, 1)
        return (Status.SUCCESS, 0)
    if business_signal in ("none", "candidate"):
        return (Status.UNKNOWN, EXIT_UNKNOWN)
    if business_signal == "sentinel":
        return _SENTINEL_MAP.get(loop_status or "", (Status.UNKNOWN, EXIT_UNKNOWN))
    # 未知 business_signal：保守视为未知。
    return (Status.UNKNOWN, EXIT_UNKNOWN)


@dataclass(frozen=True)
class Result:
    """一次角色执行的完整结果（设计 §8.1 / §9）。

    本对象经 :meth:`to_dict` 序列化后即为 CLI 的 JSON 契约（Task 7 负责
    ``json.dumps``）。字段名与顺序即为契约本身，不可随意更名或增减。

    字段语义：

    * ``role`` —— 角色名（如 ``"verify"``）。
    * ``status`` —— 归一化业务状态（:class:`Status`）。
    * ``child_exit_code`` —— 子进程真实退出码；**未启动** 时为 ``None``。
    * ``exit_code`` —— CLI 退出码。
    * ``loop_status`` —— ``stdout`` 中最后一条 ``LOOP_STATUS`` 哨兵原始值。
    * ``started_at`` / ``finished_at`` —— ISO-8601 时间戳字符串。
    * ``error`` —— 失败原因；成功时为 ``None``。
    * ``wrapper_path`` —— 实际执行的 wrapper 路径；未启动时为 ``None``。
    * ``child_stdout`` —— 子进程标准输出；未捕获时为 ``None``。
    """

    role: str
    status: Status
    child_exit_code: int | None
    exit_code: int
    loop_status: str | None
    started_at: str
    finished_at: str
    error: str | None
    wrapper_path: str | None
    child_stdout: str | None

    def to_dict(self) -> dict:
        """返回 CLI JSON 契约字典（10 个键）。

        ``status`` 序列化为其 :class:`Status` 的 ``.value`` 字符串（而非枚举
        对象本身），其余字段原样透传（含 ``None``）。
        """
        return {
            "role": self.role,
            "status": self.status.value,
            "child_exit_code": self.child_exit_code,
            "exit_code": self.exit_code,
            "loop_status": self.loop_status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "wrapper_path": self.wrapper_path,
            "child_stdout": self.child_stdout,
        }
