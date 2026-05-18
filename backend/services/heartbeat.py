"""
System Heartbeat — Proactive background AI engine.

Periodically runs background tasks to monitor health, network,
time-based triggers, and proactive notifications.
"""

import asyncio
import structlog
from datetime import datetime, timezone

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


class SystemHeartbeat:
    """
    Background heartbeat for autonomous system behaviors.
    """

    def __init__(self, event_bus: EventBus, container):
        self.event_bus = event_bus
        self.container = container
        self._running = False
        self._task: asyncio.Task | None = None
        
        self._last_media_scan: str = ""
        self._last_network_snapshot: str = ""

    async def start(self):
        """Start the heartbeat."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("heartbeat_started")

    async def stop(self):
        """Stop the heartbeat."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("heartbeat_stopped")

    async def _loop(self):
        """Main heartbeat loop. Runs every 5 minutes."""
        while self._running:
            await asyncio.sleep(300)  # 5 minutes
            
            now = datetime.now(timezone.utc)
            
            try:
                # 1. Media Library Scan (every 6 hours)
                if not self._last_media_scan or (now - datetime.fromisoformat(self._last_media_scan)).total_seconds() > 21600:
                    ml = self.container.media_library()
                    await ml.scan()
                    self._last_media_scan = now.isoformat()
                    
                # 2. Network Snapshot (every 24 hours)
                if not self._last_network_snapshot or (now - datetime.fromisoformat(self._last_network_snapshot)).total_seconds() > 86400:
                    ni = self.container.network_intelligence()
                    await ni.take_snapshot()
                    self._last_network_snapshot = now.isoformat()
                    
                # 3. Memory Cleanup / Summarization
                # (Future expansion: periodically run memory compaction)
                
            except Exception as e:
                logger.error("heartbeat_error", error=str(e))
