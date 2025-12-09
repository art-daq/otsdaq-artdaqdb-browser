"""
File: loader.py
Purpose: Configuration loading and saving utilities.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: ConfigError, ConfigLoader, MAX_BACKUP_VERSIONS
Complexity: Medium | Lines: 186
"""

import shutil
from pathlib import Path
from typing import Optional, List, Tuple
import yaml
from .schema import AppConfig

MAX_BACKUP_VERSIONS = 5


class ConfigError(Exception):
    pass


class ConfigLoader:
    DEFAULT_PATHS = [
        Path("./appconfig.yml"),
        Path("./appconfig.yaml"),
        Path("~/.ots-browser/config.yml").expanduser(),
        Path("~/.ots-browser/config.yaml").expanduser(),
    ]

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._validation_errors: List[str] = []

    def find_config_file(self) -> Optional[Path]:
        if self.config_path and self.config_path.exists():
            return self.config_path
        for path in self.DEFAULT_PATHS:
            if path.exists():
                return path
        return None

    def load(self) -> Tuple[AppConfig, List[str]]:
        warnings = []
        config_file = self.find_config_file()
        if config_file is not None:
            self.config_path = config_file
        if config_file is None:
            warnings.append("No configuration file found, using defaults")
            self._config = AppConfig()
            return (self._config, warnings)
        try:
            with open(config_file, "r") as f:
                raw_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_file}: {e}")
        except IOError as e:
            raise ConfigError(f"Cannot read {config_file}: {e}")
        try:
            self._config = AppConfig(**raw_config)
        except Exception as e:
            raise ConfigError(f"Configuration validation failed: {e}")
        return (self._config, warnings)

    def save(self, config: AppConfig, path: Optional[Path] = None) -> None:
        save_path = path or self.config_path
        if save_path is None:
            save_path = Path("~/.ots-browser/config.yaml").expanduser()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        if save_path.exists():
            self._rotate_backups(save_path)
        config_dict = config.model_dump()
        try:
            with open(save_path, "w") as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except IOError as e:
            raise ConfigError(f"Cannot write to {save_path}: {e}")
        self.config_path = save_path
        self._config = config

    def _rotate_backups(self, file_path: Path) -> None:
        oldest_backup = Path(f"{file_path}.{MAX_BACKUP_VERSIONS + 1:03d}")
        if oldest_backup.exists():
            oldest_backup.unlink()
        for i in range(MAX_BACKUP_VERSIONS, 0, -1):
            current_backup = Path(f"{file_path}.{i:03d}")
            next_backup = Path(f"{file_path}.{i + 1:03d}")
            if current_backup.exists():
                if i == MAX_BACKUP_VERSIONS:
                    current_backup.unlink()
                else:
                    shutil.move(str(current_backup), str(next_backup))
        if file_path.exists():
            first_backup = Path(f"{file_path}.001")
            shutil.copy2(str(file_path), str(first_backup))

    def validate(self, config_dict: dict) -> Tuple[bool, List[str]]:
        errors = []
        try:
            AppConfig(**config_dict)
            return (True, [])
        except Exception as e:
            errors.append(str(e))
            return (False, errors)

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            (self._config, _) = self.load()
        return self._config

    def reload(self) -> AppConfig:
        self._config = None
        (config, _) = self.load()
        return config
