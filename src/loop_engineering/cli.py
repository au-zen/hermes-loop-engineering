"""命令行入口与参数解析（参数契约见设计 §7.1）。

命令形态：

    <cli> [全局选项] <role> [-- <原生角色参数...>]
    <cli> [全局选项] run <role> [<role>...]
    <cli> [全局选项] status

全局选项必须出现在第一个非选项 token（角色 / ``run`` / ``status``）之前；
``--`` 之后的 token 原样透传给底层脚本；未使用 ``--`` 时，出现在命令之后的
选项一律视为用法错误，不做归属猜测。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

USAGE = (
    "usage: hermes-loop [全局选项] <role> [-- <原生角色参数...>]\n"
    "       hermes-loop [全局选项] run <role> [<role>...]\n"
    "       hermes-loop [全局选项] status"
)

#: 需要跟一个取值的全局选项 -> ParsedArgs 字段名。
_VALUE_OPTIONS = {
    "--workdir": "workdir",
    "--scripts": "scripts",
    "--db": "db",
}

#: 保存为布尔标志的全局选项 -> ParsedArgs 字段名。
_FLAG_OPTIONS = {
    "--json": "json",
    "--continue-on-degraded": "continue_on_degraded",
}


class UsageError(Exception):
    """命令行用法错误（由 ``main`` 映射为退出码 2）。"""


@dataclass
class ParsedArgs:
    """``parse_args`` 的解析结果。"""

    json: bool = False
    command: str = "role"
    roles: list[str] = field(default_factory=list)
    child_args: list[str] = field(default_factory=list)
    workdir: str | None = None
    scripts: str | None = None
    db: str | None = None
    continue_on_degraded: bool = False


def parse_args(argv: list[str]) -> ParsedArgs:
    """把 ``argv`` 解析为 :class:`ParsedArgs`，用法错误抛出 :class:`UsageError`。"""
    if not argv:
        raise UsageError("缺少命令：需要 <role>、run 或 status")

    result = ParsedArgs()
    seen_command = False
    in_child_args = False
    index = 0
    total = len(argv)

    while index < total:
        token = argv[index]

        # ``--`` 之后的一切原样透传（分隔符本身不含入）。
        if in_child_args:
            result.child_args.append(token)
            index += 1
            continue

        if not seen_command:
            if token == "--":
                raise UsageError("`--` 之前需要一个命令（<role>、run 或 status）")
            if token in _FLAG_OPTIONS:
                setattr(result, _FLAG_OPTIONS[token], True)
                index += 1
                continue
            if token in _VALUE_OPTIONS:
                if index + 1 >= total:
                    raise UsageError(f"{token} 需要一个取值")
                setattr(result, _VALUE_OPTIONS[token], argv[index + 1])
                index += 2
                continue
            if token.startswith("-"):
                raise UsageError(f"未知的全局选项：{token}")

            # 第一个非选项 token 即命令。
            if token in ("run", "status"):
                result.command = token
            else:
                result.command = "role"
                result.roles.append(token)
            seen_command = True
            index += 1
            continue

        # 命令之后：``--`` 开启透传，其余选项视为用法错误。
        if token == "--":
            in_child_args = True
            index += 1
            continue
        if token.startswith("-"):
            raise UsageError(
                f"选项 {token} 必须放在命令之前，或使用 `--` 透传给角色"
            )
        result.roles.append(token)
        index += 1

    if not seen_command:
        raise UsageError("缺少命令：需要 <role>、run 或 status")

    return result


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。用法错误返回 2；本任务其余命令返回占位 0。"""
    if argv is None:
        argv = sys.argv[1:]
    try:
        parse_args(argv)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
