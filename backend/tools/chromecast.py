"""
Chromecast / Google TV Tool

Allows Megan to autonomously control media on LAN Google Cast devices.
Supports basic commands like volume up/down, mute, play/pause, stop, and launching YouTube.
"""

import time
import structlog
from typing import Any

from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class ChromecastTool(BaseTool):
    name = "chromecast"
    description = (
        "Control Google Cast devices and smart TVs on the local network. "
        "Use this tool when the user asks to pause the TV, turn the volume up or down, "
        "mute the TV, stop playback, or play something on YouTube on the TV. "
        "Actions: 'play', 'pause', 'stop', 'mute', 'unmute', 'volume_up', 'volume_down', 'set_volume', 'launch_youtube'."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "The action to perform on the TV (e.g. 'play', 'pause', 'volume_up', 'volume_down', 'mute', 'launch_youtube')",
            "required": True,
        },
        "value": {
            "type": "string",
            "description": "Optional value for the action. (e.g., volume level for 'set_volume', or YouTube Video ID/Search Query for 'launch_youtube')",
        },
        "device_name": {
            "type": "string",
            "description": "Optional friendly name of the TV. If omitted, uses the first discovered device.",
        },
    }
    dangerous = False

    def __init__(self, settings=None) -> None:
        self._settings = settings

    async def execute(
        self, action: str, value: str = "", device_name: str = "", **_
    ) -> ToolResult:
        try:
            import pychromecast
            from pychromecast.controllers.youtube import YouTubeController

            logger.info("chromecast_tool_start", action=action, target=device_name or "auto")

            # Blocking call: fetch chromecasts (can take a few seconds)
            # In a truly async architecture, we'd query the lan_monitor state,
            # but for reliable execution here, we fetch it fresh.
            chromecasts, browser = pychromecast.get_listed_chromecasts(
                friendly_names=[device_name] if device_name else None
            )

            if not chromecasts:
                pychromecast.discovery.stop_discovery(browser)
                return ToolResult(
                    success=False,
                    output=f"Could not find any Chromecast device matching '{device_name}' on the network." if device_name else "No Chromecast devices found on the local network.",
                )

            cast = chromecasts[0]
            cast.wait()
            
            output_msg = ""
            mc = cast.media_controller

            if action == "play":
                mc.play()
                output_msg = f"Sent PLAY command to {cast.device.friendly_name}"
            elif action == "pause":
                mc.pause()
                output_msg = f"Sent PAUSE command to {cast.device.friendly_name}"
            elif action == "stop":
                mc.stop()
                output_msg = f"Sent STOP command to {cast.device.friendly_name}"
            elif action == "mute":
                cast.set_volume_muted(True)
                output_msg = f"Muted {cast.device.friendly_name}"
            elif action == "unmute":
                cast.set_volume_muted(False)
                output_msg = f"Unmuted {cast.device.friendly_name}"
            elif action == "volume_up":
                cast.volume_up()
                output_msg = f"Turned volume UP on {cast.device.friendly_name}"
            elif action == "volume_down":
                cast.volume_down()
                output_msg = f"Turned volume DOWN on {cast.device.friendly_name}"
            elif action == "set_volume":
                try:
                    vol = float(value)
                    if vol > 1.0:
                        vol = vol / 100.0 # Handle 0-100 scale
                    cast.set_volume(vol)
                    output_msg = f"Set volume to {vol} on {cast.device.friendly_name}"
                except ValueError:
                    return ToolResult(success=False, output="Invalid volume value. Must be a number.")
            elif action == "launch_youtube":
                yt = YouTubeController()
                cast.register_handler(yt)
                # Just launch the app for now. Playback requires actual video IDs.
                yt.launch()
                output_msg = f"Launched YouTube on {cast.device.friendly_name}"
            else:
                pychromecast.discovery.stop_discovery(browser)
                return ToolResult(success=False, output=f"Unknown action: {action}")

            # Give it a tiny moment to process
            time.sleep(0.5)
            
            # Clean up discovery
            pychromecast.discovery.stop_discovery(browser)

            return ToolResult(
                success=True,
                output=output_msg,
            )

        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="Chromecast control requires 'pychromecast'. Install with: pip install pychromecast",
            )
        except Exception as e:
            logger.error("chromecast_tool_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to execute chromecast command: {str(e)}",
            )
