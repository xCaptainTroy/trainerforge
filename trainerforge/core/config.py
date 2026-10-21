"""Local application settings. No network access and no telemetry."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "TrainerForge"


def config_path() -> Path:
    return app_data_dir() / "config.json"


def log_dir() -> Path:
    return app_data_dir() / "logs"


@dataclass
class AppConfig:
    disclaimer_accepted: bool = False
    window_geometry: str = "1280x820"
    last_table: str = ""
    last_process: str = ""

    @classmethod
    def load(cls) -> "AppConfig":
        path = config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        config = cls()
        config.disclaimer_accepted = bool(data.get("disclaimer_accepted", False))
        geometry = data.get("window_geometry")
        if isinstance(geometry, str) and geometry.strip():
            config.window_geometry = geometry.strip()
        config.last_table = str(data.get("last_table", "")) if data.get("last_table") else ""
        config.last_process = str(data.get("last_process", "")) if data.get("last_process") else ""
        return config

    def save(self) -> None:
        path = config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            os.replace(temporary, path)
        except OSError:
            # Settings are a convenience; failing to save them must not stop
            # the application or lose the user's table.
            pass
