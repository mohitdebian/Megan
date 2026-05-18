"""
Media Library — Local-first intelligent media platform.

Scans configured directories for media files, extracts metadata,
builds a searchable index, and tracks watch history with resume positions.
"""

import os
import json
import asyncio
import subprocess
import structlog
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)

# Supported media extensions
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma"}
ALL_MEDIA = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


@dataclass
class MediaFile:
    """A single indexed media file."""

    path: str
    filename: str
    media_type: str  # "video" or "audio"
    size_bytes: int = 0
    duration_seconds: float = 0
    resolution: str = ""  # e.g. "1920x1080"
    codec: str = ""
    container: str = ""
    indexed_at: str = ""
    last_played: str = ""
    resume_position: float = 0  # seconds
    play_count: int = 0
    favorite: bool = False
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MediaFile":
        return cls(**data)


@dataclass
class WatchHistoryEntry:
    """A record of something that was played."""

    path: str
    filename: str
    played_at: str
    duration_watched: float = 0
    completed: bool = False


class MediaLibrary:
    """
    Local media intelligence platform.

    Scans directories, indexes files with metadata, tracks watch history,
    and provides search + recommendation capabilities.
    """

    # Default scan directories
    DEFAULT_SCAN_DIRS = [
        os.path.expanduser("~/Videos"),
        os.path.expanduser("~/Movies"),
        os.path.expanduser("~/Music"),
        os.path.expanduser("~/Downloads"),
    ]

    def __init__(self, data_dir: Path):
        self._index_path = data_dir / "media_index.json"
        self._history_path = data_dir / "watch_history.json"
        self._files: dict[str, MediaFile] = {}  # keyed by absolute path
        self._history: list[WatchHistoryEntry] = []
        self._scan_dirs: list[str] = self.DEFAULT_SCAN_DIRS

        self._load_index()
        self._load_history()

    def _load_index(self):
        """Load media index from disk."""
        if self._index_path.exists():
            try:
                with open(self._index_path, "r") as f:
                    data = json.load(f)
                for path, file_data in data.items():
                    self._files[path] = MediaFile.from_dict(file_data)
                logger.info("media_index_loaded", count=len(self._files))
            except Exception as e:
                logger.warning("media_index_load_failed", error=str(e))

    def _save_index(self):
        """Persist media index to disk."""
        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._index_path, "w") as f:
                json.dump(
                    {k: v.to_dict() for k, v in self._files.items()},
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning("media_index_save_failed", error=str(e))

    def _load_history(self):
        """Load watch history from disk."""
        if self._history_path.exists():
            try:
                with open(self._history_path, "r") as f:
                    data = json.load(f)
                self._history = [WatchHistoryEntry(**e) for e in data]
            except Exception as e:
                logger.warning("watch_history_load_failed", error=str(e))

    def _save_history(self):
        """Persist watch history to disk."""
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_path, "w") as f:
                json.dump([asdict(e) for e in self._history[-500:]], f, indent=2)
        except Exception as e:
            logger.warning("watch_history_save_failed", error=str(e))

    async def scan(self) -> int:
        """Scan all configured directories for media files. Returns count of new files."""
        new_count = 0
        now = datetime.now(timezone.utc).isoformat()

        for scan_dir in self._scan_dirs:
            if not os.path.isdir(scan_dir):
                continue

            for root, _, files in os.walk(scan_dir):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in ALL_MEDIA:
                        continue

                    full_path = os.path.join(root, filename)

                    # Skip already indexed files (unless modified)
                    if full_path in self._files:
                        continue

                    media_type = "video" if ext in VIDEO_EXTENSIONS else "audio"

                    try:
                        size = os.path.getsize(full_path)
                    except OSError:
                        continue

                    media = MediaFile(
                        path=full_path,
                        filename=filename,
                        media_type=media_type,
                        size_bytes=size,
                        container=ext.lstrip("."),
                        indexed_at=now,
                    )

                    # Try to extract metadata via ffprobe
                    meta = await self._probe_metadata(full_path)
                    if meta:
                        media.duration_seconds = meta.get("duration", 0)
                        media.resolution = meta.get("resolution", "")
                        media.codec = meta.get("codec", "")

                    self._files[full_path] = media
                    new_count += 1

        if new_count > 0:
            self._save_index()
            logger.info("media_scan_complete", new_files=new_count, total=len(self._files))

        return new_count

    async def _probe_metadata(self, path: str) -> dict | None:
        """Extract metadata using ffprobe (non-blocking)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode != 0:
                return None

            data = json.loads(stdout)
            result = {}

            # Duration from format
            fmt = data.get("format", {})
            result["duration"] = float(fmt.get("duration", 0))

            # Video stream info
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    w = stream.get("width", 0)
                    h = stream.get("height", 0)
                    result["resolution"] = f"{w}x{h}" if w and h else ""
                    result["codec"] = stream.get("codec_name", "")
                    break

            return result
        except Exception:
            return None

    def search(self, query: str, media_type: str = "") -> list[MediaFile]:
        """Search media files by name, fuzzy match."""
        query_lower = query.lower()
        results = []

        for media in self._files.values():
            if query_lower in media.filename.lower() or query_lower in media.path.lower():
                if media_type and media.media_type != media_type:
                    continue
                results.append(media)

        # Sort by relevance (exact filename match first, then by play count)
        results.sort(key=lambda m: (
            0 if query_lower == m.filename.lower().rsplit(".", 1)[0] else 1,
            -m.play_count,
        ))

        return results[:20]

    def get_recent(self, limit: int = 10) -> list[MediaFile]:
        """Get recently played media."""
        played = [m for m in self._files.values() if m.last_played]
        played.sort(key=lambda m: m.last_played, reverse=True)
        return played[:limit]

    def get_favorites(self) -> list[MediaFile]:
        """Get favorite media."""
        return [m for m in self._files.values() if m.favorite]

    def get_resumable(self) -> list[MediaFile]:
        """Get media that can be resumed (has a saved position)."""
        return [
            m for m in self._files.values()
            if m.resume_position > 0 and m.resume_position < m.duration_seconds * 0.95
        ]

    def record_playback(self, path: str, position: float = 0, completed: bool = False):
        """Record that a file was played."""
        now = datetime.now(timezone.utc).isoformat()

        if path in self._files:
            media = self._files[path]
            media.last_played = now
            media.play_count += 1
            if not completed and position > 0:
                media.resume_position = position
            elif completed:
                media.resume_position = 0

        entry = WatchHistoryEntry(
            path=path,
            filename=os.path.basename(path),
            played_at=now,
            duration_watched=position,
            completed=completed,
        )
        self._history.append(entry)

        self._save_index()
        self._save_history()

    def toggle_favorite(self, path: str) -> bool:
        """Toggle favorite status. Returns new state."""
        if path in self._files:
            self._files[path].favorite = not self._files[path].favorite
            self._save_index()
            return self._files[path].favorite
        return False

    def get_stats(self) -> dict:
        """Get library statistics."""
        videos = [m for m in self._files.values() if m.media_type == "video"]
        audio = [m for m in self._files.values() if m.media_type == "audio"]
        total_size = sum(m.size_bytes for m in self._files.values())
        total_duration = sum(m.duration_seconds for m in self._files.values())

        return {
            "total_files": len(self._files),
            "videos": len(videos),
            "audio": len(audio),
            "total_size_gb": round(total_size / (1024**3), 2),
            "total_duration_hours": round(total_duration / 3600, 1),
            "favorites": len(self.get_favorites()),
            "resumable": len(self.get_resumable()),
        }

    def get_recommendations(self, limit: int = 5) -> list[MediaFile]:
        """
        Simple recommendation engine based on:
        - Recently added but never played
        - Popular (high play count) files
        """
        never_played = [m for m in self._files.values() if m.play_count == 0]
        never_played.sort(key=lambda m: m.indexed_at, reverse=True)

        popular = sorted(self._files.values(), key=lambda m: m.play_count, reverse=True)

        recommendations = []
        # Mix: 3 new + 2 popular
        for m in never_played[:3]:
            if m not in recommendations:
                recommendations.append(m)
        for m in popular[:2]:
            if m not in recommendations:
                recommendations.append(m)

        return recommendations[:limit]
