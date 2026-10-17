# hermes-loop-engineering

Hermes Loop 的统一 CLI 薄调度器。

把一组 loop 角色脚本收敛为单一入口 `hermes-loop`：**不改变底层脚本行为、不迁移调度配置、不重新实现 Agent 调用**。CLI 只负责三件事——解析路径、启动前校验、把执行结果如实转换为退出码与结构化输出。

## 作为 Hermes Skill / Tap 使用

本仓库同时是一个 Hermes skill tap：skill 目录为 `skills/hermes-loop-engineering/`（**只含 `SKILL.md`，不含 prompts**）。

> **skill 只负责说明，CLI 需另装。** 从 GitHub 安装 skill 时只会复制被引用的 skill 文件，Python 包本体不会随之安装。

安装 CLI：

```bash
uv tool install git+https://github.com/au-zen/hermes-loop-engineering
```

安装 skill（任选其一；tap 搜索在某些版本不稳定，推荐直接按仓库路径安装）：

```bash
hermes skills install au-zen/hermes-loop-engineering/skills/hermes-loop-engineering
# 或：
hermes skills tap add au-zen/hermes-loop-engineering
```

### Cron 配置

```bash
# no_agent job（经 hermes-loop-*.sh wrapper 调用 CLI）
hermes cron edit <job_id> --script "hermes-loop-collector.sh"
```

### 手动执行

```bash
hermes-loop <role> [-- <args...>]   # 执行单个角色
hermes-loop run <role> [<role>...]  # 顺序执行角色序列
hermes-loop status                  # 查看状态摘要
hermes-loop --json status           # JSON 输出
```

## 状态

**已实现（v1）。** 单角色执行、`run` 顺序执行与 `status` 均已接线并通过测试。

### 安装

```bash
uv sync
```

### 命令

```bash
hermes-loop <role> [-- <原生角色参数...>]   # 执行单个角色
hermes-loop run <role> [<role>...]          # 顺序执行角色序列（无默认流水线）
hermes-loop status                          # 调用配置的状态脚本查看摘要
```

### 全局选项

全局选项必须出现在命令之前：`--json`、`--workdir`、`--scripts`、`--db`、
`--continue-on-degraded`。

- 取值类选项支持 `--opt value` 与 `--opt=value` 两种写法；`--opt value` 的取值
  **不能以 `-` 开头**（避免吞掉下一个 flag），需要时改用 `--opt=value`。
- `--` 之后的参数**原样透传**给底层脚本，且**仅 `role` 命令支持**。
- 未使用 `--` 时，命令之后出现的未识别选项按**用法错误**处理（不猜测归属）。
- 命令之后的多余位置参数按**用法错误**处理：`role` 只接受一个角色名，`status`
  不接受任何参数；`run` 只接受角色名（**不接受** `--` 透传——同一串参数发给多个
  角色语义不明）。

### 环境变量

显式参数优先级最高；未给出时回落环境变量，再回落默认值：

| 变量 | 对应 | 默认 |
|---|---|---|
| `HERMES_LOOP_WORKDIR` | `--workdir` | `~/.hermes` |
| `HERMES_LOOP_SCRIPTS` | `--scripts` | `<workdir>/scripts` |
| `HERMES_LOOP_DB` | `--db` | `~/.hermes/db/loop_state.duckdb` |

### 退出码

`0` 成功；`2` 用法错误（未知角色、多余位置参数、非法全局选项取值、`run --`）；
`3` unknown；`4` degraded；
`5` wrapper 启动前/启动期失败；`128+N` 子进程被信号 N 杀死；
`130` SIGINT。子进程非零退出码**原样透传**。

> **契约（重要）：退出码只能保证「`0` = 未失败，非 `0` = 未成功」这一二元判断。**
> 因为子进程非零码原样透传，`2`/`3`/`4` 会与 CLI 约定含义**发生冲突**
> —— 脚本自己返回 `2` 与 CLI 的「用法错误」无法从退出码区分。
> **凡需要区分具体状态（尤其是 CLI 状态 vs 子进程自报状态）时，必须使用 `--json`。**
> 补充：`LOOP_STATUS` 权威词表为 4 值（`ok|fallback_ok|degraded|failed`），
> v1 注册表内无 `sentinel` 角色；`none`/`candidate` 角色一律 `unknown`(3)。

### 角色与信号来源

| 角色 | 信号来源 | 说明 |
|---|---|---|
| `collector` | `exit_code` | 唯一以脚本退出码判定的角色；失败路径确有非 0 退出 |
| `fixer`、`trust_audit` | `candidate` | 无可信业务信号 → 一律 `unknown`(3) |
| 其余 7 个 | `none` | 无可信业务信号 → 一律 `unknown`(3) |

**推论：`run` 只适合 `exit_code` 角色（v1 仅 `collector`）。** 其余角色放进 `run`
会因 `unknown` 立即停止并返回 `3`——这是刻意的「绝不把未知当成功」。

### `--json` 契约

* 单角色与 `status`：stdout 为**恰好一个**可解析 JSON 对象。
* `run`：stdout 为**恰好一个**对象 `{"command": "run", "steps": [<result>, ...]}`，
  `steps` 含每个已执行步骤（含最终停止的那一步）。
* 子进程 stderr 始终继承到 CLI stderr，不污染 `--json` stdout。

### v1 范围限制

* 不设超时（无 timeout）。
* `status` 以 `uv run python` 调用配置的状态脚本（无 `.sh` wrapper）。
* SIGINT（`130`）不负责清理子进程，超出 v1 范围。

## 约定

1. 状态在 CLI 边界转换；底层脚本的状态约定与退出码惯例**保持不变**。
2. `--workdir` / `--scripts` / `--db` 决定所有路径；CLI 不按角色名动态推导路径，
   只使用注册表中固定登记的映射。
3. 启动子进程前校验 wrapper 是否存在且可执行，否则以启动失败退出（`5`）。
4. 只要读到显式 `LOOP_STATUS: failed` 哨兵即按失败处理（即使退出码为 `0`），
   绝不把失败伪装成成功；词表说明行（取值后含 `|`）不算哨兵。

## 贡献 / 维护

贡献流程与发布前泄露门禁见 [CONTRIBUTING.md](CONTRIBUTING.md)。
