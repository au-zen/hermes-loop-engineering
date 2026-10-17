---
name: hermes-loop-engineering
description: Use when running, scheduling, or debugging Hermes Loop engineering roles through the `hermes-loop` CLI — a thin dispatcher that maps loop role scripts to exit codes and `--json` output.
version: 0.1.0
metadata:
  hermes:
    tags: [hermes, loop, cli, automation, cron, scheduler]
---

# Hermes Loop Engineering

`hermes-loop` 是一个薄调度器：它只做三件事——解析路径、启动前校验 wrapper、把子进程结果如实转换为退出码与结构化输出。它不重新实现角色逻辑，也不管理 loop 状态。

## 何时使用

- 运行单个 loop 角色，或按顺序运行一串角色。
- 把 loop 角色接进 cron。
- 以程序方式读取角色结果（`--json`）。
- 排查某角色「失败 / 成功」的判定。

## 安装（skill 只管说明，CLI 需另装）

本 skill 只包含 `SKILL.md`。真正的 CLI（`hermes-loop` 命令）需单独安装：

```bash
uv tool install git+https://github.com/au-zen/hermes-loop-engineering
```

安装 skill 本身（任选其一）：

```bash
# 直接按仓库路径安装（推荐；tap 搜索在某些版本不稳定）
hermes skills install au-zen/hermes-loop-engineering/skills/hermes-loop-engineering

# 或把仓库加为 tap，再浏览安装
hermes skills tap add au-zen/hermes-loop-engineering
```

## 步骤

```bash
hermes-loop <role> [-- <原生角色参数...>]   # 执行单个角色
hermes-loop run <role> [<role>...]          # 顺序执行角色序列（fail-fast）
hermes-loop status                          # 查看状态摘要
hermes-loop --json <role|run|status>        # 机器可读输出
```

全局选项（必须放在命令之前）：`--json`、`--workdir`、`--scripts`、`--db`、`--continue-on-degraded`。

`~/.hermes/scripts/hermes-loop-<role>.sh` 这类 cron wrapper 会 `exec hermes-loop <role>`，因此需先装好上面的 CLI。

## 常见坑

- 全局选项必须出现在命令之前；命令之后的未知选项按**用法错误**处理。
- `--` 之后的参数**原样透传**，且**仅 `role` 命令支持**；`run` 不接受 `--`。
- 取值类选项的 `--opt value` 形式，取值**不能以 `-` 开头**（避免吞掉下一个 flag）；需要时用 `--opt=value`。
- 退出码只能保证「`0` = 未失败，非 `0` = 未成功」。子进程非零码原样透传，`2/3/4` 会与 CLI 约定含义冲突——**要区分具体状态必须用 `--json`**。
- 读到显式 `LOOP_STATUS: failed` 哨兵即按失败处理，即使退出码为 `0`。
- **`none`/`candidate` 角色即使脚本成功也判为 `unknown`（退出码 3）**——CLI 只区分「进程成功」与「业务状态已知」，这两类角色在 v1 没有可信业务信号。因此 `run` 遇 `unknown` 即停止，**`run` 只适合 `exit_code` 角色（v1 仅 `collector`）**；把这些角色放进 `run` 会每次都停在第 3 码。
- `LOOP_STATUS` 权威词表为 4 值：`ok|fallback_ok|degraded|failed`。v1 注册表内**没有 `sentinel` 角色**，故该分支当前不可达；缺失或未知哨兵一律 `unknown`(3)。词表待首个真正输出哨兵的角色出现时再定稿（issue #1）。

## 验证方法

```bash
# 命令存在（无参数 → 用法错误，退出码 2）
hermes-loop; echo "rc=$?"

# 机器可读状态
hermes-loop --json status
```

退出码：`0` 成功；`2` 用法错误；`3` unknown；`4` degraded；`5` 启动失败；`128+N` 信号；`130` SIGINT。子进程非零退出码**原样透传**。

环境变量（显式参数优先）：`HERMES_LOOP_WORKDIR`（默认 `~/.hermes`）、`HERMES_LOOP_SCRIPTS`、`HERMES_LOOP_DB`。完整契约见仓库 `README.md`。
