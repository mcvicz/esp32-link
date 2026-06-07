"""Singleton configuration store persisted to ``~/.config/esp32-link/config.json``."""

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from threading import Lock
from typing import ClassVar, Self

logger = logging.getLogger(__name__)

CONFIG_PATH: Path = Path.home() / ".config" / "esp32-link" / "config.json"
DEFAULT_URL: str = "ws://192.168.4.1:81/ws"


@dataclass
class Config:
    """Persistent user settings.

    Access via :meth:`Config.instance` (Singleton). The first access loads from
    :data:`CONFIG_PATH` if it exists; defaults are used otherwise.
    """

    last_url: str = DEFAULT_URL
    window_geometry: str | None = None

    _instance: ClassVar[Self | None] = None
    _lock: ClassVar[Lock] = Lock()

    @classmethod
    def instance(cls) -> Self:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._load()
        return cls._instance

    @classmethod
    def _load(cls) -> Self:
        if not CONFIG_PATH.exists():
            return cls()
        try:
            data = json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("failed to read config (%s); using defaults", exc)
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        CONFIG_PATH.write_text(json.dumps(payload, indent=2))

    @classmethod
    def reset(cls) -> None:
        """Drop the cached singleton. For tests."""
        with cls._lock:
            cls._instance = None
