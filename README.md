# hermes-loop-engineering

Hermes Loop Engineering 的**统一 CLI 薄调度器**（独立 repo）。

把现有 loop 角色脚本（no_agent 层）收敛为一个统一入口 `loop`，
不改变底层脚本行为、不迁移 cron、不重新实现 Agent 调用。

## 状态

**设计阶段。** 设计文档待批准后进入实施计划。

→ [`docs/superpowers/specs/2026-10-17-hermes-loop-engineering-design.md`](docs/superpowers/specs/2026-10-17-hermes-loop-engineering-design.md)

## 边界（硬约束）

1. `~/.hermes/scripts/` 是**唯一生产脚本来源**；`automation/loop-engineering` skill 内的副本仅作参考，不得覆盖生产脚本。
2. 首版只包装**已审核的 no_agent 角色**；`analyzer` / `reviewer` / `digest` 等纯 Agent 角色继续由 cron + prompt 驱动。
3. 底层 cron 契约（`LOOP_STATUS` 协议、`exit 0` 惯例）**保持不变**；状态在 CLI 边界转换。
4. DuckDB 默认 `~/.hermes/db/loop_state.duckdb`，禁止使用根目录陈旧库。
