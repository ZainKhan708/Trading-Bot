"""Configuration management utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping

import yaml


@dataclass
class ConfigManager:
    """Centralised loader for YAML and JSON strategy configuration files."""

    search_paths: Iterable[Path]

    def __post_init__(self) -> None:
        self._search_paths = [Path(p) for p in self.search_paths]

    def load(self, name: str) -> Dict[str, Any]:
        path = self._resolve(name)
        if path.suffix in {".yml", ".yaml"}:
            return self._load_yaml(path)
        if path.suffix == ".json":
            return self._load_json(path)
        raise ValueError(f"Unsupported config file type: {path.suffix}")

    def _resolve(self, name: str) -> Path:
        candidate = Path(name)
        if candidate.is_file():
            return candidate
        for base in self._search_paths:
            path = base / name
            if path.is_file():
                return path
        raise FileNotFoundError(f"Configuration '{name}' not found in search paths")

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return ConfigManager._ensure_dict(data, path)

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return ConfigManager._ensure_dict(data, path)

    @staticmethod
    def _ensure_dict(data: Any, path: Path) -> Dict[str, Any]:
        if not isinstance(data, MutableMapping):
            raise ValueError(f"Configuration '{path}' must define a mapping")
        return dict(data)


def merge_dicts(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries for layered configs."""

    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(value, Mapping)
        ):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
