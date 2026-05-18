"""
Code Monitor — Watches a sandbox directory for Python script crashes.

Uses watchdog to detect file saves, runs the script, and if it crashes,
triggers the HealerAgent to autonomously fix it.
"""

import asyncio
import uuid
import structlog
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from core.events import EventBus, Event, EventType
from agent.healer import HealerAgent

logger = structlog.get_logger(__name__)

# Debounce map to avoid double-triggers from editors that save twice
_last_modified: dict[str, float] = {}
DEBOUNCE_SECONDS = 3.0


class _PythonFileHandler(FileSystemEventHandler):
    """Watchdog handler that detects .py file modifications."""

    def __init__(self, loop: asyncio.AbstractEventLoop, callback):
        super().__init__()
        self._loop = loop
        self._callback = callback

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".py"):
            return

        import time
        now = time.time()
        last = _last_modified.get(event.src_path, 0)
        if now - last < DEBOUNCE_SECONDS:
            return
        _last_modified[event.src_path] = now

        # Schedule the async callback on the event loop
        asyncio.run_coroutine_threadsafe(
            self._callback(event.src_path), self._loop
        )


class CodeMonitor:
    """
    Monitors ~/projects/sandbox/ for Python file changes.
    When a .py file is saved, runs it. If it crashes, triggers the Healer.
    """

    def __init__(self, event_bus: EventBus, watch_dir: str = None):
        self.event_bus = event_bus
        self.healer = HealerAgent()
        self._observer: Observer | None = None
        self._is_running = False

        # Default watch directory
        if watch_dir:
            self._watch_dir = Path(watch_dir)
        else:
            self._watch_dir = Path.home() / "projects" / "sandbox"

    async def start(self):
        """Start watching the sandbox directory."""
        if self._is_running:
            return

        # Ensure directory exists
        self._watch_dir.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        handler = _PythonFileHandler(loop, self._on_file_changed)

        self._observer = Observer()
        self._observer.schedule(handler, str(self._watch_dir), recursive=True)
        self._observer.daemon = True
        self._observer.start()

        self._is_running = True
        logger.info("code_monitor_started", watch_dir=str(self._watch_dir))

    async def stop(self):
        """Stop watching."""
        self._is_running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None
        logger.info("code_monitor_stopped")

    async def _on_file_changed(self, file_path: str):
        """Called when a .py file is modified. Runs it and heals if needed."""
        path = Path(file_path)
        logger.info("code_monitor_file_changed", file=path.name)

        try:
            # Run the script
            proc = await asyncio.create_subprocess_exec(
                "python3", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(path.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 0:
                logger.info("code_monitor_script_ok", file=path.name)
                return  # All good, nothing to do

            # Script crashed — extract traceback
            traceback_text = stderr.decode(errors="ignore")
            logger.warning("code_monitor_crash_detected", file=path.name, error=traceback_text[:200])

            # Trigger the healer
            result = await self.healer.heal(file_path, traceback_text)

            if result["success"]:
                # Announce the fix via TTS
                message = f"Sir, your script {path.name} crashed with an error. I have already patched it and verified the fix works."
                await self.event_bus.emit(
                    Event(
                        type=EventType.SYSTEM_NOTIFICATION,
                        data={"message": message},
                        conversation_id=str(uuid.uuid4()),
                    )
                )
            else:
                # Announce that we couldn't fix it
                message = f"Sir, your script {path.name} crashed, but I wasn't able to automatically fix it. The error was: {result['original_error'][:100]}"
                await self.event_bus.emit(
                    Event(
                        type=EventType.SYSTEM_NOTIFICATION,
                        data={"message": message},
                        conversation_id=str(uuid.uuid4()),
                    )
                )

        except asyncio.TimeoutError:
            logger.warning("code_monitor_script_timeout", file=path.name)
        except Exception as e:
            logger.error("code_monitor_error", file=path.name, error=str(e))
