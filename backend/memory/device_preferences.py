"""
Device Preferences Memory — Tracks user habits for automation.

Stores preferred default devices, average listening volumes,
and most-used scenes to personalize the ecosystem.
"""

import json
import structlog
from typing import Any
from pathlib import Path

logger = structlog.get_logger(__name__)


class DevicePreferencesMemory:
    """
    Manages persistent preferences for the physical environment.
    """

    def __init__(self, data_dir: Path):
        self._db_path = data_dir / "device_preferences.json"
        self._prefs: dict[str, Any] = {
            "default_tv": None,           # UUID of preferred TV
            "default_speaker": None,      # UUID of preferred speaker
            "preferred_volumes": {},      # { uuid: int }
            "scene_usage": {},            # { scene_name: int (count) }
            "last_used_scene": None,      # name of last scene
            "automation_habits": {},      # Extensible habits dictionary
        }
        self._load()

    def _load(self):
        if self._db_path.exists():
            try:
                with open(self._db_path, "r") as f:
                    data = json.load(f)
                    # Merge with defaults
                    self._prefs.update(data)
            except Exception as e:
                logger.warning("device_prefs_load_failed", error=str(e))

    def _save(self):
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._db_path, "w") as f:
                json.dump(self._prefs, f, indent=2)
        except Exception as e:
            logger.warning("device_prefs_save_failed", error=str(e))

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a specific preference."""
        return self._prefs.get(key, default)

    def set_preference(self, key: str, value: Any):
        """Set a specific preference."""
        self._prefs[key] = value
        self._save()

    def record_scene_usage(self, scene_name: str):
        """Track that a scene was used."""
        usage = self._prefs.get("scene_usage", {})
        usage[scene_name] = usage.get(scene_name, 0) + 1
        self._prefs["scene_usage"] = usage
        self._prefs["last_used_scene"] = scene_name
        self._save()

    def record_preferred_volume(self, device_uuid: str, volume: int):
        """Track the preferred volume for a device."""
        vols = self._prefs.get("preferred_volumes", {})
        
        # Keep a rolling average if it exists, or just set it
        existing = vols.get(device_uuid)
        if existing is not None:
            # Weight new volume at 30%, old at 70% for slow learning
            new_vol = int((existing * 0.7) + (volume * 0.3))
            vols[device_uuid] = new_vol
        else:
            vols[device_uuid] = volume
            
        self._prefs["preferred_volumes"] = vols
        self._save()

    def get_preferred_volume(self, device_uuid: str, default_fallback: int = 20) -> int:
        """Get the learned preferred volume for a device."""
        vols = self._prefs.get("preferred_volumes", {})
        return vols.get(device_uuid, default_fallback)
