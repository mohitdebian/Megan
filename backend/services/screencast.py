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

        logger.info("screencast_starting", hls_dir=str(self._hls_dir))
        
        import mss
        self._sct = mss.MSS()
        self._mon = self._sct.monitors[1]  # primary monitor
        width = self._mon["width"]
        height = self._mon["height"]

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pixel_format", "bgra",
            "-video_size", f"{width}x{height}",
            "-framerate", "15",
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments",
            "-hls_segment_filename", str(self._hls_dir / "segment_%03d.ts"),
            str(playlist_path)
        ]

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        self._is_active = True
        self._capture_task = asyncio.create_task(self._capture_loop())

        # Wait a few seconds for ffmpeg to generate the first segments
        await asyncio.sleep(3)

        if self._process.returncode is not None:
            raise RuntimeError(f"FFmpeg exited immediately with code {self._process.returncode}")

        logger.info("screencast_active")
        return str(playlist_path)

    async def _capture_loop(self):
        """Continuously grab frames via mss and write to ffmpeg stdin."""
        try:
            while self._is_active and self._process and self._process.stdin:
                sct_img = self._sct.grab(self._mon)
                try:
                    self._process.stdin.write(sct_img.bgra)
                    await self._process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
                await asyncio.sleep(1/15.0)  # ~15 fps
        except Exception as e:
            logger.error("screencast_loop_error", error=str(e))
        finally:
            if self._process and self._process.stdin:
                try:
                    self._process.stdin.close()
                except Exception:
                    pass

    async def stop(self):
        """Stop the screencast."""
        self._is_active = False
        
        if hasattr(self, "_capture_task") and self._capture_task:
            self._capture_task.cancel()
            
        if hasattr(self, "_sct") and self._sct:
            self._sct.close()

        if self._process:
            logger.info("screencast_stopping")
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()
            except Exception:
                pass
            self._process = None
            
        # Cleanup
        for f in self._hls_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        
        logger.info("screencast_stopped")
