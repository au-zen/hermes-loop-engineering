---
name: hermes-loop-engineering
description: Use when operating Hermes Loop engineering roles — invoking or scheduling the `hermes-loop` CLI (collector, log_scanner, canary, verify, fixer, decide, learn, notify, trust_audit, daily_diagnostic) or interpreting its exit codes and `--json` output.
version: 0.1.0
metadata:
  hermes:
    tags: [hermes, loop, cli, automation, cron, scheduler, roles]
---

# Hermes Loop Engineering

## Overview

`hermes-loop` is a thin dispatcher over a fixed set of loop "role" scripts. It does three things only: resolve paths, pre-flight the wrapper, and convert the child result into an exit code plus optional JSON. It never re-implements role logic or manages loop state.

## When to use

- Running a single loop role or a sequence of roles.
- Wiring loop roles into cron (`hermes cron … --script hermes-loop-<role>.sh`).
- Reading a role's result programmatically (`--json`).
- Debugging why a role "failed" versus "succeeded".

## Quick reference

```bash
hermes-loop <role> [-- <args...>]     # one role
hermes-loop run <role> [<role>...]    # sequential, fail-fast
hermes-loop status                    # status summary (delegates to a status script)
hermes-loop --json <role|run|status>  # machine-readable
```

Global options (must precede the command): `--json`, `--workdir`, `--scripts`, `--db`, `--continue-on-degraded`.

## Exit codes

`0` success · `2` usage error · `3` unknown · `4` degraded · `5` start failure · `128+N` signal · `130` SIGINT. Child non-zero exit codes pass through raw.

**Contract:** the exit code only guarantees the binary judgement `0 = did not fail`, non-zero = not successful. Because child codes pass through, `2/3/4` can collide with CLI meanings. When you must distinguish CLI state from a role's own status, **use `--json`**.

## Prompts

`prompts/` holds templates for the LLM phases (ANALYZE / REVIEW / DIGEST). Replace the `<...>` placeholders with your own table names and commands before use.

## Setup

```bash
git clone <repo-url> ~/.hermes/skills/automation/hermes-loop-engineering
cd ~/.hermes/skills/automation/hermes-loop-engineering && uv sync
uv tool install .   # puts the `hermes-loop` command on PATH
```

See README.md for full usage, environment variables, and the exit-code contract.
