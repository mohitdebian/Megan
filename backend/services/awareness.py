"""
Situational Awareness Engine (SAE) — "Always Watching".

Monitors the user's idle time, system load, and running applications
to proactively trigger interventions or helpful AI comments.
"""

import asyncio
import uuid
import psutil
import structlog
from datetime import datetime

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)

# Constants for state tracking
IDLE_THRESHOLD_MS = 10 * 60 * 1000  # 10 minutes to be considered "Away"
HEAVY_CPU_THRESHOLD = 90.0          # 90% CPU usage
HEAVY_RAM_THRESHOLD = 90.0          # 90% RAM usage


class AwarenessEngine:
    """
    Background service that monitors the system state every 30 seconds
    and triggers autonomous interventions based on a rules engine.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._is_running = False
        self._task: asyncio.Task | None = None
        
        # State History
        self._was_away = False
        self._heavy_process_counter = {}

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("awareness_engine_started")

    async def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("awareness_engine_stopped")

    async def _loop(self):
        # Wait a bit after startup
        await asyncio.sleep(20)
        
        while self._is_running:
            try:
                await self._evaluate_situation()
            except Exception as e:
                logger.error("awareness_eval_error", error=str(e))
                
            await asyncio.sleep(30)

    async def _evaluate_situation(self):
        # 1. Idle Time Context
        idle_ms = await self._get_idle_time_ms()
        is_away = idle_ms > IDLE_THRESHOLD_MS
        
        # Rule: Welcome Back
        if self._was_away and not is_away:
            # User just returned after being away for > 10 mins
            logger.info("user_returned_active", idle_was=idle_ms)
            await self._announce(
                "Welcome back, Sir. I hope you had a good break. I'll let you know if anything important came up."
            )
            # Reset
            self._was_away = False
        elif is_away:
            self._was_away = True
            
        # If the user is currently away, don't bother them with other notifications
        if is_away:
            return

        # 2. System Load Context
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_usage = psutil.virtual_memory().percent
        
        # Rule: Resource Hog Detection
        if cpu_usage > HEAVY_CPU_THRESHOLD or ram_usage > HEAVY_RAM_THRESHOLD:
            # Find the culprit
            top_process = None
            max_val = 0
            
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    val = p.info['cpu_percent'] if cpu_usage > HEAVY_CPU_THRESHOLD else p.info['memory_percent']
                    if val and val > max_val:
                        max_val = val
                        top_process = p.info['name']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            if top_process and top_process not in ['gnome-shell', 'Xwayland']:
                count = self._heavy_process_counter.get(top_process, 0) + 1
                self._heavy_process_counter[top_process] = count
                
                # If the same process is heavy for 3 consecutive checks (90 seconds)
                if count == 3:
                    logger.warning("resource_hog_detected", process=top_process, cpu=cpu_usage, ram=ram_usage)
                    metric = "CPU" if cpu_usage > HEAVY_CPU_THRESHOLD else "RAM"
                    await self._announce(
                        f"Sir, I noticed that {top_process} is using a massive amount of {metric}. Would you like me to kill the process?"
                    )
            else:
                self._heavy_process_counter.clear()
        else:
            self._heavy_process_counter.clear()

        # 3. Late Night Coding Context
        now = datetime.now()
        if now.hour >= 1 and now.hour <= 4:
            # It's between 1 AM and 4 AM
            coding_apps = ["code", "pycharm", "nvim", "vim", "sublime"]
            is_coding = False
            for p in psutil.process_iter(['name']):
                if p.info.get('name') in coding_apps:
                    is_coding = True
                    break
                    
            if is_coding:
                # We only want to say this once per night. 
                # A simple hack: just check if the minute is exactly 0 or 30 (every half hour)
                if now.minute == 0 and now.second < 30:
                    await self._announce(
                        "Sir, it's getting quite late and you are still coding. Please remember to take a break soon."
                    )

    async def _get_idle_time_ms(self) -> int:
        """
        Get the exact idle time in milliseconds using GNOME Mutter DBus.
        """
        try:
            # busctl --user call org.gnome.Mutter.IdleMonitor /org/gnome/Mutter/IdleMonitor/Core org.gnome.Mutter.IdleMonitor GetIdletime
            proc = await asyncio.create_subprocess_exec(
                "busctl", "--user", "call", "org.gnome.Mutter.IdleMonitor",
                "/org/gnome/Mutter/IdleMonitor/Core", "org.gnome.Mutter.IdleMonitor", "GetIdletime",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                # Output format is typically: "t 1063\n"
                out_str = stdout.decode().strip()
                if out_str.startswith("t "):
                    return int(out_str[2:])
        except Exception as e:
            logger.debug("idle_time_fetch_error", error=str(e))
            
        return 0

    async def _announce(self, message: str):
        """Emit a system notification to be spoken aloud."""
        await self.event_bus.emit(
            Event(
                type=EventType.SYSTEM_NOTIFICATION,
                data={"message": message},
                conversation_id=str(uuid.uuid4())
            )
        )
