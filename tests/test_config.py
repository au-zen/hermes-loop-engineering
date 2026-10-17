import os, sys, pathlib, pytest
from loop_engineering.config import (Config, resolve_config, wrapper_path,
                                     child_env, preflight, StartError)
from loop_engineering.roles import ROLES

def test_defaults_point_at_production_paths(monkeypatch):
    monkeypatch.delenv("HERMES_LOOP_WORKDIR", raising=False)
    cfg = resolve_config(env={})
    assert cfg.workdir == os.path.expanduser("~/.hermes")
    assert cfg.scripts_dir == os.path.join(cfg.workdir, "scripts")
    assert cfg.db_path == os.path.expanduser("~/.hermes/db/loop_state.duckdb")

def test_flags_override_env_override_defaults():
    cfg = resolve_config(workdir="/w", scripts="/s", db="/d", env={})
    assert (cfg.workdir, cfg.scripts_dir, cfg.db_path) == ("/w", "/s", "/d")

def test_child_env_passes_loop_vars():
    cfg = Config("/w", "/s", "/d")
    e = child_env(cfg, base_env={"PATH": "/x"})
    assert e["HERMES_LOOP_WORKDIR"] == "/w"
    assert e["HERMES_LOOP_SCRIPTS"] == "/s"
    assert e["HERMES_LOOP_DB"] == "/d" and e["PATH"] == "/x"

def test_preflight_missing_wrapper_raises(tmp_path):
    cfg = Config(str(tmp_path), str(tmp_path), str(tmp_path / "x.duckdb"))
    with pytest.raises(StartError):
        preflight(ROLES["verify"], cfg)

def test_preflight_broken_symlink_raises(tmp_path):   # Review Focus #1
    link = tmp_path / "loop_auto_verify.sh"
    link.symlink_to(tmp_path / "nowhere")
    cfg = Config(str(tmp_path), str(tmp_path), str(tmp_path / "x.duckdb"))
    with pytest.raises(StartError):
        preflight(ROLES["verify"], cfg)

def test_preflight_non_executable_raises(tmp_path):
    f = tmp_path / "loop_auto_verify.sh"; f.write_text("#!/bin/bash\n"); f.chmod(0o644)
    cfg = Config(str(tmp_path), str(tmp_path), str(tmp_path / "x.duckdb"))
    with pytest.raises(StartError):
        preflight(ROLES["verify"], cfg)

def test_preflight_ok_returns_abs_path(tmp_path):
    f = tmp_path / "loop_auto_verify.sh"; f.write_text("#!/bin/bash\n"); f.chmod(0o755)
    cfg = Config(str(tmp_path), str(tmp_path), str(tmp_path / "x.duckdb"))
    assert preflight(ROLES["verify"], cfg) == str(f)
