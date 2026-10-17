"""角色注册表：角色 → 显式 wrapper 文件名 + 能力元数据（设计 §5/§5.1）。

这是一个**固定映射表**：wrapper 文件名逐项显式登记，绝不按角色名动态拼接
路径。仅登记有生产脚本入口的 10 个白名单角色；纯 Agent 角色
（``analyzer``/``reviewer``/``digest``）与无 cron 绑定的手动工具
（``reality_check``/``integrity``）**不登记**。
"""

from __future__ import annotations

from dataclasses import dataclass

#: ``RoleSpec.business_signal`` 的合法取值。
BUSINESS_SIGNALS = frozenset({"exit_code", "sentinel", "none", "candidate"})


@dataclass(frozen=True)
class RoleSpec:
    """单个角色的固定 wrapper 映射与能力元数据。

    :param name: 角色名（``ROLES`` 的键）。
    :param wrapper: wrapper 文件名（相对 scripts 目录，固定登记，不动态拼接）。
    :param business_signal: 业务信号来源，∈ ``BUSINESS_SIGNALS``。
    :param run_eligible: 是否可纳入 ``run`` 批量执行（v1 仅 ``collector``）。
    """

    name: str
    wrapper: str
    business_signal: str
    run_eligible: bool

    def __post_init__(self) -> None:
        # 构造期即校验，避免 ``BUSINESS_SIGNALS`` 沦为无人消费的常量。
        if self.business_signal not in BUSINESS_SIGNALS:
            raise ValueError(
                f"非法 business_signal：{self.business_signal!r}"
                f"（角色 {self.name!r}；合法取值 {sorted(BUSINESS_SIGNALS)}）"
            )


class UnknownRoleError(Exception):
    """请求的角色不在白名单注册表中。"""


#: 白名单角色注册表（固定映射，逐项显式登记）。
ROLES: dict[str, RoleSpec] = {
    "collector": RoleSpec(
        name="collector",
        wrapper="cron_loop_collector.sh",
        business_signal="exit_code",
        run_eligible=True,
    ),
    "log_scanner": RoleSpec(
        name="log_scanner",
        wrapper="loop_hermes_log_scanner.sh",
        business_signal="none",
        run_eligible=False,
    ),
    "canary": RoleSpec(
        name="canary",
        wrapper="loop_canary_injector.sh",
        business_signal="none",
        run_eligible=False,
    ),
    "verify": RoleSpec(
        name="verify",
        wrapper="loop_auto_verify.sh",
        business_signal="none",
        run_eligible=False,
    ),
    "fixer": RoleSpec(
        name="fixer",
        wrapper="loop_auto_fixer.sh",
        business_signal="candidate",
        run_eligible=False,
    ),
    "decide": RoleSpec(
        name="decide",
        wrapper="loop_auto_decide.sh",
        business_signal="none",
        run_eligible=False,
    ),
    "learn": RoleSpec(
        name="learn",
        wrapper="loop_learn.sh",
        business_signal="none",
        run_eligible=False,
    ),
    "notify": RoleSpec(
        name="notify",
        wrapper="_loop_notify.sh",
        business_signal="none",
        run_eligible=False,
    ),
    "trust_audit": RoleSpec(
        name="trust_audit",
        wrapper="loop_trust_audit.sh",
        business_signal="candidate",
        run_eligible=False,
    ),
    "daily_diagnostic": RoleSpec(
        name="daily_diagnostic",
        wrapper="_cron_loop_diag.sh",
        business_signal="none",
        run_eligible=False,
    ),
}


def get_role(name: str) -> RoleSpec:
    """返回 ``name`` 对应的 :class:`RoleSpec`；不在白名单时抛 :class:`UnknownRoleError`。"""
    try:
        return ROLES[name]
    except KeyError:
        raise UnknownRoleError(f"未登记的角色：{name!r}") from None
