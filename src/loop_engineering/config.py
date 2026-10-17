"""配置解析与 wrapper 启动前校验（设计 §4/§5）。

本模块是薄调度器的“事实来源”之一：

* :func:`resolve_config` 按 **显式参数 > 环境变量 > 默认值** 的优先级解析出
  一个不可变的 :class:`Config`。
* :func:`wrapper_path` 只根据 :class:`~loop_engineering.roles.RoleSpec` 中
  固定登记的 wrapper 文件名拼接路径，**绝不按角色名动态推导**。
* :func:`child_env` 把三枚 loop 变量透传给子进程（仅透传，不承诺子进程消费）。
* :func:`preflight` 在启动子进程前校验 wrapper 是否存在且可执行，否则抛
  :class:`StartError`。

所有路径默认指向生产位置，但测试通过显式参数/``env`` 注入，不触碰真实
``~/.hermes``。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .roles import RoleSpec

#: 环境变量名 → :class:`Config` 字段名。
ENV_WORKDIR = "HERMES_LOOP_WORKDIR"
ENV_SCRIPTS = "HERMES_LOOP_SCRIPTS"
ENV_DB = "HERMES_LOOP_DB"


class StartError(Exception):
    """wrapper 在启动前校验失败（缺失、断链或不可执行）。"""


@dataclass(frozen=True)
class Config:
    """解析后的运行配置。

    :param workdir: Hermes 工作目录。
    :param scripts_dir: wrapper 脚本所在目录。
    :param db_path: DuckDB 状态库文件路径。
    """

    workdir: str
    scripts_dir: str
    db_path: str


def _default_workdir() -> str:
    return os.path.expanduser("~/.hermes")


def resolve_config(
    workdir: str | None = None,
    scripts: str | None = None,
    db: str | None = None,
    env: dict | None = None,
) -> Config:
    """解析配置，优先级为 **显式参数 > 环境变量 > 默认值**。

    :param workdir: 显式工作目录；``None`` 时回落到环境变量/默认值。
    :param scripts: 显式 scripts 目录；``None`` 时回落到环境变量，再回落到
        ``<workdir>/scripts``。
    :param db: 显式 DuckDB 路径；``None`` 时回落到环境变量，再回落到
        ``~/.hermes/db/loop_state.duckdb``。
    :param env: 环境变量映射；``None`` 时使用 :data:`os.environ`。传入 ``{}``
        可屏蔽真实环境（测试用）。
    :returns: 解析后的 :class:`Config`。
    """
    environ = os.environ if env is None else env

    resolved_workdir = (
        workdir
        if workdir is not None
        else environ.get(ENV_WORKDIR) or _default_workdir()
    )

    resolved_scripts = scripts if scripts is not None else environ.get(ENV_SCRIPTS)
    if resolved_scripts is None:
        resolved_scripts = os.path.join(resolved_workdir, "scripts")

    resolved_db = db if db is not None else environ.get(ENV_DB)
    if resolved_db is None:
        resolved_db = os.path.expanduser("~/.hermes/db/loop_state.duckdb")

    return Config(
        workdir=resolved_workdir,
        scripts_dir=resolved_scripts,
        db_path=resolved_db,
    )


def wrapper_path(spec: RoleSpec, cfg: Config) -> str:
    """返回 ``spec`` 在 ``cfg.scripts_dir`` 下的 wrapper 绝对/拼接路径。

    wrapper 文件名取自固定注册表 :class:`~loop_engineering.roles.RoleSpec`
    的 ``wrapper`` 字段，**不** 从角色名推导。
    """
    return os.path.join(cfg.scripts_dir, spec.wrapper)


def child_env(cfg: Config, base_env: dict | None = None) -> dict:
    """基于 ``base_env``（默认 :data:`os.environ`）复制并注入 loop 变量。

    注入的三枚变量仅作透传；本工具不承诺子进程实际消费它们。
    """
    env = dict(os.environ if base_env is None else base_env)
    env[ENV_WORKDIR] = cfg.workdir
    env[ENV_SCRIPTS] = cfg.scripts_dir
    env[ENV_DB] = cfg.db_path
    return env


def preflight(spec: RoleSpec, cfg: Config) -> str:
    """启动前校验 wrapper，成功返回其路径，失败抛 :class:`StartError`。

    校验两件事：

    1. ``os.path.isfile(path)`` —— 跟随软链，断链会返回 ``False``。
    2. ``os.access(path, os.X_OK)`` —— 是否具备可执行权限。
    """
    path = wrapper_path(spec, cfg)
    if not os.path.isfile(path):
        raise StartError(
            f"wrapper 缺失或不可用（可能是断链）：角色 {spec.name!r} → {path}"
        )
    if not os.access(path, os.X_OK):
        raise StartError(
            f"wrapper 不可执行：角色 {spec.name!r} → {path}（请 chmod +x）"
        )
    return path
