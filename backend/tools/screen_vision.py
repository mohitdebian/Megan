"""
Screen Vision Tool — Captures the user's screen and returns it as an image block.

Megan can "see" the user's screen by calling this tool. It uses the `mss` library
to capture a screenshot of the primary monitor, compresses it to JPEG, and returns
it as an Anthropic-compatible image content block that the LLM can analyze.
"""

import base64
import structlog
from io import BytesIO
from tools.base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class ScreenVisionTool(BaseTool):
    name = "analyze_screen"
    description = (
        "Capture a screenshot of the user's current screen and analyze it. "
        "Use this when the user asks you to look at their screen, read something "
        "on-screen, help with code visible on their monitor, debug a visible error, "
        "or when they say things like 'look at this', 'what do you see', "
        "'what's on my screen', 'read this', or 'what's wrong with this code'. "
        "Returns the screenshot as an image that you can analyze and describe."
    )
    parameters = {
        "query": {
            "type": "string",
            "description": "What the user wants to know about their screen (e.g., 'what IDE am I using', 'read this error', 'what is wrong with this code')",
            "required": True,
        },
        "monitor": {
            "type": "integer",
            "description": "Which monitor to capture (1 = primary, 2 = secondary, etc.). Defaults to 1.",
        },
    }
    dangerous = False

    def __init__(self, settings=None) -> None:
        self._settings = settings

    async def execute(self, query: str = "", monitor: int = 1, **_) -> ToolResult:
        try:
            import asyncio
            def _capture():
                import mss
                from PIL import Image
    
                with mss.MSS() as sct:
                    # Validate monitor index
                    mon_idx = monitor
                    if mon_idx < 1 or mon_idx >= len(sct.monitors):
                        mon_idx = 1
    
                    mon = sct.monitors[mon_idx]
                    logger.info(
                        "screen_capture_start",
                        monitor=mon_idx,
                        width=mon["width"],
                        height=mon["height"],
                    )
    
                    # Grab the screen
                    sct_img = sct.grab(mon)
    
                    # Convert to PIL Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    
                    # Downscale if larger than 1920x1080 to save tokens/bandwidth
                    max_w, max_h = 1920, 1080
                    if img.width > max_w or img.height > max_h:
                        img.thumbnail((max_w, max_h), Image.LANCZOS)
    
                    # Compress to JPEG
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=75)
                    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
                    logger.info(
                        "screen_capture_done",
                        size_kb=round(len(b64_data) * 3 / 4 / 1024, 1),
                        resolution=f"{img.width}x{img.height}",
                    )
                    
                    return b64_data, img.width, img.height

            b64_data, width, height = await asyncio.to_thread(_capture)

            # Build Anthropic-compatible multimodal content blocks
            content_blocks = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64_data,
                    },
                },
                {
                    "type": "text",
                    "text": f"The above is a live screenshot of the user's screen. The user asked: \"{query}\". Please analyze the screenshot and respond to their question.",
                },
            ]

            return ToolResult(
                success=True,
                output=f"[Screenshot captured: {width}x{height}]",
                content_blocks=content_blocks,
            )

        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="Screen capture requires 'mss' and 'Pillow' packages. Install with: pip install mss Pillow",
            )
        except Exception as e:
            logger.error("screen_capture_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to capture screen: {str(e)}",
            )
