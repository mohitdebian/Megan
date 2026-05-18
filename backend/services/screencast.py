"""
Screencast Service — Manages live ffmpeg screen encoding to HLS.

Captures the user's desktop using x11grab (via XWayland) and encodes
it into an HTTP Live Streaming (HLS) playlist for the Chromecast.
"""

import os
import shutil
import asyncio
import structlog
from pathlib import Path

logger = structlog.get_logger(__name__)


class ScreencastService:
    def __init__(self, data_dir: Path):
        self._hls_dir = data_dir / "screencast"
        self._process: asyncio.subprocess.Process | None = None
        self._is_active = False

        # Ensure directory is clean
        if self._hls_dir.exists():
            shutil.rmtree(self._hls_dir, ignore_errors=True)
        self._hls_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_active(self) -> bool:
        return self._is_active and self._process is not None and self._process.returncode is None

    async def start(self) -> str:
        """Start the screencast and return the HLS playlist path."""
        if self.is_active:
            await self.stop()

        # Clean old segments
        for f in self._hls_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass

        playlist_path = self._hls_dir / "stream.m3u8"
        display = os.environ.get("DISPLAY", ":1")

        logger.info("screencast_starting", display=display, hls_dir=str(self._hls_dir))

        cmd = [
            "ffmpeg",
            "-f", "x11grab",
            "-video_size", "1920x1080",  # Assume standard fallback; ideally detect
            "-framerate", "30",
            "-i", display,
            "-c:v", "libx264",
            "-preset", "ultrafast",     # Low latency, higher bitrates
            "-tune", "zerolatency",     # Crucial for live casting
            "-pix_fmt", "yuv420p",      # Required by Chromecast
            "-f", "hls",
            "-hls_time", "2",           # 2-second segments
            "-hls_list_size", "5",      # Keep last 5 segments in playlist
            "-hls_flags", "delete_segments",
            "-hls_segment_filename", str(self._hls_dir / "segment_%03d.ts"),
            str(playlist_path)
        ]

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        # Wait a few seconds for ffmpeg to generate the first segments
        # so the Chromecast doesn't 404 immediately
        await asyncio.sleep(3)

        if self._process.returncode is not None:
            raise RuntimeError(f"FFmpeg exited immediately with code {self._process.returncode}")

        self._is_active = True
        logger.info("screencast_active")
        return str(playlist_path)

    async def stop(self):
        """Stop the screencast."""
        if self._process:
            logger.info("screencast_stopping")
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
            
        self._is_active = False
        
        # Cleanup
        for f in self._hls_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        
        logger.info("screencast_stopped")
