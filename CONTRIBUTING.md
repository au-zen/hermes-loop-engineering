# 贡献 / 维护

## 发布前检查（泄露门禁）

推送前必须运行本地泄露检查（通用模式 + 本地标识符清单）：

```bash
bash scripts/check_leaks.sh                       # 扫描工作区（git 追踪文件）
bash scripts/check_leaks.sh <remote>..<local>     # 扫描本次要推送的提交
```

- `scripts/check_leaks.sh` 只含**通用**模式；具体标识符放在被 gitignore 的
  `scripts/leak_denylist.local` 中，脚本运行时读取（该文件不进仓库、也不进 CI）。
- `scripts/pre-push` 是可选的本地 hook：对**本次推送范围**逐个跑检查，失败即中止
  推送。安装：`ln -sf ../../scripts/pre-push .git/hooks/pre-push`。
- **hook 只是本地约束**，换机器或 `--no-verify` 即失效，所以 CI
  （`.github/workflows/leak-check.yml`）会在 push / PR 时再跑一遍**通用模式**检查。

> 教训：泄露检查脚本本身不得嵌入具体标识符——否则它就把清单变成了新的泄露面。
