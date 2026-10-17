# hermes-loop-engineering

Hermes Loop 的统一 CLI 薄调度器。

把一组 loop 角色脚本收敛为单一入口 `hermes-loop`：**不改变底层脚本行为、不迁移调度配置、不重新实现 Agent 调用**。CLI 只负责三件事——解析路径、启动前校验、把执行结果如实转换为退出码与结构化输出。

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
> 补充：`skipped`/`dry-run` 在 v1 注册表中不可达；一旦未来引入 `sentinel` 角色，
> `0` 将不再唯一对应成功，届时同样以 `--json` 为准。

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
