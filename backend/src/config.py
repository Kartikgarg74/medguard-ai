"""Configuration loader with YAML parsing and env var substitution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _substitute_env_vars(obj: Any) -> Any:
    """Recursively substitute ${ENV_VAR} patterns with actual environment variables."""
    if isinstance(obj, str):
        pattern = re.compile(r"\$\{(\w+)\}")

        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return pattern.sub(replacer, obj)
    elif isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values take precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Loads and merges YAML configuration with env var substitution."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"

        env_path = self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        self._config: dict = {}

    def load(self) -> dict:
        """Load configuration from YAML + environment variables."""
        default_path = self.config_dir / "default.yaml"
        if default_path.exists():
            with open(default_path) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

        self._config = _substitute_env_vars(self._config)
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-separated key. E.g., 'ai.groq.api_key'."""
        if not self._config:
            self.load()
        keys = key.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val


# Global config instance
_config = Config()


def get_config() -> Config:
    return _config
