"""Tests for configuration loader."""

import os
from pathlib import Path

from src.config import Config, _substitute_env_vars, _deep_merge


def test_env_var_substitution():
    os.environ["TEST_VAR"] = "hello"
    result = _substitute_env_vars("value is ${TEST_VAR}")
    assert result == "value is hello"
    del os.environ["TEST_VAR"]


def test_env_var_missing_returns_empty():
    result = _substitute_env_vars("${NONEXISTENT_VAR}")
    assert result == ""


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}, "e": 5}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3}, "e": 5}


def test_deep_merge_does_not_mutate():
    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    _deep_merge(base, override)
    assert base == {"a": {"b": 1}}


def test_config_load_default(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text("database:\n  path: test.db\n")

    cfg = Config(project_root=tmp_path)
    result = cfg.load()
    assert result["database"]["path"] == "test.db"


def test_config_get_dot_notation(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text("database:\n  path: test.db\n")

    cfg = Config(project_root=tmp_path)
    cfg.load()
    assert cfg.get("database.path") == "test.db"
    assert cfg.get("nonexistent.key", "default") == "default"
