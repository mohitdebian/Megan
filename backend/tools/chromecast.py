"""
Chromecast / Google TV Tool

Allows Megan to autonomously control media on LAN Google Cast devices.
Uses DeviceManager for instant device lookup and connection caching for reliability.
"""

import time
import asyncio
import structlog
from typing import Any

from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)

# Connection cache: { uuid: pychromecast.Chromecast }
_cast_cache: dict[str, Any] = {}


class ChromecastTool(BaseTool):
    name = "chromecast"
    description = (
        "Control Google Cast devices and smart TVs on the local network. "
        "Use this tool when the user asks to pause the TV, turn the volume up or down, "
        "mute the TV, stop playback, play something on YouTube, cast a local media file to the TV, "
        "or start/stop screencasting (live casting their computer screen to the TV). "
        "Actions: 'play', 'pause', 'stop', 'mute', 'unmute', 'volume_up', 'volume_down', "
        "'set_volume', 'launch_youtube', 'play_youtube', 'cast_local_media', 'status', "
        "'start_screencast', 'stop_screencast'."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": (
                "The action to perform. One of: play, pause, stop, mute, unmute, "
                "volume_up, volume_down, set_volume, launch_youtube, play_youtube, "
                "cast_local_media, status, start_screencast, stop_screencast"
            ),
            "required": True,
        },
        "value": {
            "type": "string",
            "description": "Optional value. Volume level (0-100) for set_volume, video_id for play_youtube, or absolute file path for cast_local_media.",
        },
        "device_name": {
            "type": "string",
            "description": "Optional friendly name of the TV. If omitted, uses the first online device.",
        },
    }
    dangerous = False

    VALID_ACTIONS = {
        "play", "pause", "stop", "mute", "unmute",
        "volume_up", "volume_down", "set_volume",
        "launch_youtube", "play_youtube", "cast_local_media", "status",
        "start_screencast", "stop_screencast",
    }

    def __init__(self, settings=None, device_manager=None, screencast_service=None) -> None:
        self._settings = settings
        self.device_manager = device_manager
        self.screencast_service = screencast_service

    def _get_cached_cast(self, device):
        """Get or create a cached pychromecast connection."""
        import pychromecast
        import uuid as uuid_mod

        cached = _cast_cache.get(device.uuid)
        if cached:
            # Verify it's still alive
            try:
                if cached.socket_client and cached.socket_client.is_connected:
                    return cached
            except Exception:
                pass
            # Dead connection, remove from cache
            _cast_cache.pop(device.uuid, None)

        # Create new connection
        device_uuid = uuid_mod.UUID(device.uuid) if len(device.uuid) == 32 else uuid_mod.uuid4()
        cast = pychromecast.get_chromecast_from_host((
            device.ip,
            device.port,
            device_uuid,
            device.model,
            device.friendly_name,
        ))
        cast.wait()
        _cast_cache[device.uuid] = cast
        return cast

    async def execute(
        self, action: str, value: str = "", device_name: str = "", **_
    ) -> ToolResult:
        # Validate action
        if action not in self.VALID_ACTIONS:
            return ToolResult(
                success=False,
                output=f"Unknown action: '{action}'. Valid actions: {', '.join(sorted(self.VALID_ACTIONS))}",
            )

        try:
            import pychromecast
            from pychromecast.controllers.youtube import YouTubeController

            logger.info("chromecast_tool_start", action=action, target=device_name or "auto")

            # --- Device Resolution via DeviceManager ---
            device = None
            if self.device_manager:
                device = self.device_manager.get_device(device_name)

            if not device:
                return ToolResult(
                    success=False,
                    output=(
                        f"No device matching '{device_name}' found on the network."
                        if device_name
                        else "No online Chromecast devices found. Is the TV powered on and connected to Wi-Fi?"
                    ),
                )

            if not device.is_online:
                return ToolResult(
                    success=False,
                    output=f"Device '{device.friendly_name}' is currently offline. Try powering it on.",
                )

            # --- Connection with Retry ---
            cast = None
            last_error = ""
            for attempt in range(3):
                try:
                    cast = self._get_cached_cast(device)
                    break
                except Exception as e:
                    last_error = str(e)
                    _cast_cache.pop(device.uuid, None)
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))  # backoff

            if not cast:
                return ToolResult(
                    success=False,
                    output=f"Failed to connect to '{device.friendly_name}' after 3 attempts: {last_error}",
                )

            name = device.friendly_name
            mc = cast.media_controller

            # --- Execute Action ---
            if action == "status":
                status = cast.status
                media_status = mc.status
                vol = int((status.volume_level or 0) * 100)
                muted = status.volume_muted
                app = status.display_name or "None"
                media_title = getattr(media_status, "title", "Nothing playing")
                player_state = getattr(media_status, "player_state", "UNKNOWN")
                output_msg = (
                    f"📺 {name}\n"
                    f"  App: {app}\n"
                    f"  Volume: {vol}% {'(muted)' if muted else ''}\n"
                    f"  Playing: {media_title}\n"
                    f"  State: {player_state}"
                )
            elif action == "play":
                mc.play()
                output_msg = f"▶️ Sent PLAY to {name}"
            elif action == "pause":
                mc.pause()
                output_msg = f"⏸️ Sent PAUSE to {name}"
            elif action == "stop":
                mc.stop()
                output_msg = f"⏹️ Sent STOP to {name}"
            elif action == "mute":
                cast.set_volume_muted(True)
                output_msg = f"🔇 Muted {name}"
            elif action == "unmute":
                cast.set_volume_muted(False)
                output_msg = f"🔊 Unmuted {name}"
            elif action == "volume_up":
                cast.volume_up()
                output_msg = f"🔊 Volume UP on {name}"
            elif action == "volume_down":
                cast.volume_down()
                output_msg = f"🔉 Volume DOWN on {name}"
            elif action == "set_volume":
                try:
                    vol = float(value)
                    if vol > 1.0:
                        vol = vol / 100.0
                    cast.set_volume(vol)
                    output_msg = f"🔊 Volume set to {int(vol * 100)}% on {name}"
                except ValueError:
                    return ToolResult(success=False, output="Invalid volume. Provide a number 0-100.")
            elif action == "launch_youtube":
                yt = YouTubeController()
                cast.register_handler(yt)
                yt.launch()
                output_msg = f"📺 Launched YouTube on {name}"
            elif action == "play_youtube":
                if not value:
                    return ToolResult(
                        success=False,
                        output="Provide the YouTube video_id in 'value' for play_youtube.",
                    )
                yt = YouTubeController()
                cast.register_handler(yt)
                yt.play_video(value)
                output_msg = f"📺 Playing YouTube video {value} on {name}"
            elif action == "cast_local_media":
                import urllib.parse
                from core.network_utils import get_local_ip

                if not value:
                    return ToolResult(
                        success=False,
                        output="Provide the absolute file path in 'value' for cast_local_media.",
                    )

                local_ip = get_local_ip()
                encoded_path = urllib.parse.quote(value)
                stream_url = f"http://{local_ip}:8000/api/media/stream?path={encoded_path}"

                content_type = "video/mp4"
                if value.endswith(".mkv"):
                    content_type = "video/x-matroska"
                elif value.endswith(".webm"):
                    content_type = "video/webm"
                elif value.endswith(".mp3"):
                    content_type = "audio/mp3"
                elif value.endswith(".avi"):
                    content_type = "video/x-msvideo"

                mc.play_media(stream_url, content_type)
                mc.block_until_active()
                output_msg = f"🎬 Streaming local file to {name}"
            elif action == "start_screencast":
                if not self.screencast_service:
                    return ToolResult(success=False, output="Screencast service not available.")
                
                from core.network_utils import get_local_ip
                
                # Start ffmpeg pipeline
                playlist_path = await self.screencast_service.start()
                
                local_ip = get_local_ip()
                # The static files are mounted at /api/screencast in main.py
                stream_url = f"http://{local_ip}:8000/api/screencast/stream.m3u8"
                
                # Wait an extra second to ensure ffmpeg wrote the initial segment
                await asyncio.sleep(1)
                
                mc.play_media(stream_url, "application/x-mpegurl")
                mc.block_until_active()
                output_msg = f"🖥️ Live screencast started on {name}"
            elif action == "stop_screencast":
                if self.screencast_service:
                    await self.screencast_service.stop()
                mc.stop()
                output_msg = f"⏹️ Screencast stopped on {name}"
            else:
                return ToolResult(success=False, output=f"Unhandled action: {action}")

            time.sleep(0.3)

            return ToolResult(success=True, output=output_msg)

        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="pychromecast not installed. Run: pip install pychromecast",
            )
        except Exception as e:
            logger.error("chromecast_tool_error", error=str(e))
            # Clear cache on error
            if device:
                _cast_cache.pop(device.uuid, None)
            return ToolResult(
                success=False,
                output="",
                error=f"Chromecast command failed: {str(e)}",
            )
