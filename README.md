# hermes-loop-engineering

Hermes Loop Engineering 的**统一 CLI 薄调度器**（独立 repo）。

把现有 loop 角色脚本（no_agent 层）收敛为一个统一入口 `loop`，
不改变底层脚本行为、不迁移 cron、不重新实现 Agent 调用。

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
hermes-loop status                          # 调用 quick_status.py 查看状态
```

全局选项（必须出现在命令之前）：`--json`、`--workdir`、`--scripts`、`--db`、
`--continue-on-degraded`。

### 环境变量

显式参数优先级最高；未给出时回落环境变量，再回落默认值：

| 变量 | 对应 | 默认 |
|---|---|---|
| `HERMES_LOOP_WORKDIR` | `--workdir` | `~/.hermes` |
| `HERMES_LOOP_SCRIPTS` | `--scripts` | `<workdir>/scripts` |
| `HERMES_LOOP_DB` | `--db` | `~/.hermes/db/loop_state.duckdb` |

### 退出码

`0` 成功；`2` 用法错误（含未知角色）；`3` unknown；`4` degraded；
`5` wrapper 启动前/启动期失败；`128+N` 子进程被信号 N 杀死；
`130` SIGINT。子进程非零退出码**原样透传**。

> **契约（重要）：退出码只能保证「`0` = 未失败，非 `0` = 未成功」这一二元判断。**
> 因为子进程非零码原样透传，`2`/`3`/`4` 会与 CLI 约定含义**发生冲突**
> —— 脚本自己返回 `2` 与 CLI 的「用法错误」无法从退出码区分。
> **凡需要区分具体状态（尤其是 CLI 状态 vs 子进程自报状态）时，必须使用 `--json`。**
> 补充：`skipped`/`dry-run` 在 v1 注册表中不可达；一旦未来引入 `sentinel` 角色，
> `0` 将不再唯一对应成功，届时同样以 `--json` 为准。

### `--json` 契约

* 单角色与 `status`：stdout 为**恰好一个**可解析 JSON 对象。
* `run`：stdout 为**恰好一个**对象 `{"command": "run", "steps": [<result>, ...]}`，
  `steps` 含每个已执行步骤（含最终停止的那一步）。
* 子进程 stderr 始终继承到 CLI stderr，不污染 `--json` stdout。

### v1 范围限制

* 不设超时（无 timeout）。
* 仅 `collector` 标记为 `run_eligible`。
* `status` 以 `uv run python quick_status.py` 调用（无 `.sh` wrapper）。
* SIGINT（`130`）不负责清理子进程，超出 v1 范围。

→ [`docs/superpowers/specs/2026-10-17-hermes-loop-engineering-design.md`](docs/superpowers/specs/2026-10-17-hermes-loop-engineering-design.md)

## 边界（硬约束）

1. `~/.hermes/scripts/` 是**唯一生产脚本来源**；`automation/loop-engineering` skill 内的副本仅作参考，不得覆盖生产脚本。
2. 首版只包装**已审核的 no_agent 角色**；`analyzer` / `reviewer` / `digest` 等纯 Agent 角色继续由 cron + prompt 驱动。
3. 底层 cron 契约（`LOOP_STATUS` 协议、`exit 0` 惯例）**保持不变**；状态在 CLI 边界转换。
4. DuckDB 默认 `~/.hermes/db/loop_state.duckdb`，禁止使用根目录陈旧库。
