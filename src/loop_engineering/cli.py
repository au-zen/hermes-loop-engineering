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

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

from .config import Config, child_env, resolve_config
from .output import Status
from .roles import UnknownRoleError, get_role
from .runner import run_role

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
            # `--opt=value` 形式：取值以 `-` 开头时唯一的合法写法。
            if token.startswith("--") and "=" in token:
                name, _, value = token.partition("=")
                if name in _VALUE_OPTIONS:
                    setattr(result, _VALUE_OPTIONS[name], value)
                    index += 1
                    continue
            if token in _VALUE_OPTIONS:
                if index + 1 >= total:
                    raise UsageError(f"{token} 需要一个取值")
                value = argv[index + 1]
                if value.startswith("-"):
                    # 不静默吞掉下一个 flag（如 `--scripts --json`）。
                    raise UsageError(
                        f"{token} 的取值不能以 `-` 开头：{value!r}"
                        f"（如确为路径请用 {token}={value}）"
                    )
                setattr(result, _VALUE_OPTIONS[token], value)
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

        # 命令之后：仅 `role` 支持 `--` 透传；位置参数仅 `run` 接受。
        if token == "--":
            if result.command != "role":
                raise UsageError(
                    f"`{result.command}` 不支持 `--` 透传"
                    "（`run` 把同一串参数发给多个角色语义不明）"
                )
            in_child_args = True
            index += 1
            continue
        if token.startswith("-"):
            raise UsageError(
                f"选项 {token} 必须放在命令之前，或使用 `--` 透传给角色"
            )
        if result.command != "run":
            # 每个角色命令用法为 `<role> [-- <args>]`；第二个位置参数是用法错误。
            raise UsageError(
                f"命令 {result.command!r} 不接受额外位置参数：{token!r}"
                "（用法：<role> [-- <args>]）"
            )
        result.roles.append(token)
        index += 1

    if not seen_command:
        raise UsageError("缺少命令：需要 <role>、run 或 status")

    return result


def _resolve(args: ParsedArgs):
    """按「显式参数 > 环境变量 > 默认值」解析运行配置。"""
    return resolve_config(
        workdir=args.workdir, scripts=args.scripts, db=args.db
    )


def _run_single(args: ParsedArgs) -> int:
    """``role`` 命令：解析角色 → 执行 wrapper → 输出结果。"""
    try:
        spec = get_role(args.roles[0])
    except UnknownRoleError as exc:
        # 未知角色视同用法错误：stderr + 退出码 2。
        print(f"error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    cfg = _resolve(args)
    result = run_role(spec, args.child_args, cfg)

    if args.json:
        # 只输出恰好一行 JSON；子进程日志留在 child_stdout 字段内，绝不泄漏到 stdout。
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        sys.stdout.write(result.child_stdout or "")
        if result.error:
            # 启动前/启动期失败在默认模式下也必须在 stderr 可见（退出码不变）。
            print(f"error: {result.error}", file=sys.stderr)
    return result.exit_code


def _run_status(args: ParsedArgs) -> int:
    """``status`` 命令：调用 ``quick_status.py``，透传其 stdout 与退出码。"""
    cfg = _resolve(args)
    # quick_status.py 无 ``.sh`` wrapper，故与生产 wrapper 一致地经 ``uv run python`` 调用。
    command = ["uv", "run", "python", os.path.join(cfg.scripts_dir, "quick_status.py")]
    if args.json:
        # 全局 ``--json`` 由 status 处理器附加到子进程参数（R6）。
        command.append("--json")

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, env=child_env(cfg), cwd=cfg.workdir
        )
    except OSError as exc:
        print(f"error: 无法启动 quick_status.py：{exc}", file=sys.stderr)
        return 5

    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    # 信号死亡（returncode < 0）按 128 + N 约定映射，绝不透传负数。
    if completed.returncode < 0:
        return 128 + (-completed.returncode)
    return completed.returncode


def run_sequence(
    roles: list[str],
    cfg: Config,
    emit_json: bool,
    continue_on_degraded: bool,
) -> int:
    """按给定顺序执行角色序列并返回退出码（设计 §9，无默认流水线）。

    语义：

    * 空序列即用法错误（抛 :class:`UsageError`，由 ``main`` 映射为 ``2``）。
    * **所有角色在执行前整体校验**：任一未知角色立即 stderr + ``2``，
      绝不先执行前面的角色（避免半执行副作用）。
    * 逐个同步执行：前一步结束后才启动下一步；**不重试、不跳过**。
    * ``emit_json`` 为真时，输出**恰好一个** JSON 对象
      ``{"command": "run", "steps": [<result.to_dict()>, ...]}``
      （R9；含最终停止的那一步）。``steps`` 之外的任何内容都不写 stdout。

    §9.2 策略表：

    * ``success`` → 继续；
    * ``degraded`` → 仅当 ``continue_on_degraded`` 为真时继续，否则停止；
    * ``failure`` / ``unknown`` → 停止。

    :param roles: 显式角色名序列（首个失败即终止后续角色）。
    :param cfg: 解析后的运行配置。
    :param emit_json: 是否以单个 JSON 对象输出全部步骤。
    :param continue_on_degraded: ``--continue-on-degraded`` 是否生效。
    :return: 最后一个已执行步骤的 CLI 退出码（全 ``success`` 时为 ``0``）。
    """
    if not roles:
        raise UsageError("run 至少需要一个角色（无默认流水线）")

    # Fix 3：先整体校验，任何未知角色在执行任何角色之前失败（退出码 2）。
    specs = []
    for name in roles:
        try:
            specs.append(get_role(name))
        except UnknownRoleError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            return 2

    last_exit_code = 0
    steps = []
    for spec in specs:
        result = run_role(spec, [], cfg)
        steps.append(result)

        if not emit_json:
            # 默认模式仍逐步透传子进程 stdout。
            sys.stdout.write(result.child_stdout or "")
            # issue #2：默认模式下启动失败等 error 也必须在 stderr 可见，
            # 否则失败只表现为一个非 0 退出码、无可读原因（fail-fast 缺口）。
            if result.error:
                print(f"error: {result.error}", file=sys.stderr)

        # §9.2 策略表：每个 Status 分支显式处理（R8 要求穷尽枚举）。
        status = result.status
        if status is Status.SUCCESS:
            last_exit_code = result.exit_code
            continue
        if status is Status.DEGRADED and continue_on_degraded:
            last_exit_code = result.exit_code
            continue
        # FAILURE / UNKNOWN → 立即停止，透传该步退出码。
        last_exit_code = result.exit_code
        break

    if emit_json:
        # R9：恰好一个可解析 JSON 对象，含全部已执行步骤（含停止步）。
        payload = {"command": "run", "steps": [r.to_dict() for r in steps]}
        print(json.dumps(payload, ensure_ascii=False))
    return last_exit_code


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：解析 → 分发；用法错误返回 2。"""
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = parse_args(argv)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    try:
        if args.command == "role":
            return _run_single(args)
        if args.command == "status":
            return _run_status(args)
        if args.command == "run":
            try:
                return run_sequence(
                    args.roles, _resolve(args), args.json, args.continue_on_degraded
                )
            except UsageError as exc:
                print(f"error: {exc}", file=sys.stderr)
                print(USAGE, file=sys.stderr)
                return 2
        raise AssertionError(f"未知命令：{args.command!r}")  # pragma: no cover
    except KeyboardInterrupt:
        # 设计 §12：SIGINT → 130。子进程清理超出 v1 范围（见 README）。
        print("error: interrupted（SIGINT）", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
