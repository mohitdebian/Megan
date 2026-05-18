"""
Automation Engine — Event-driven and time-based automation rules.

Subscribes to the EventBus and triggers automated actions based on
device events, time-of-day, and user-defined rules.
"""

import asyncio
import structlog
from dataclasses import dataclass, field
from typing import Any, Callable
from datetime import datetime, timezone

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


@dataclass
class AutomationRule:
    """A single automation rule."""

    name: str
    description: str
    trigger_type: str  # "event", "schedule", "condition"
    trigger_event: EventType | None = None
    trigger_condition: Callable | None = None
    schedule_hour: int | None = None  # 0-23 for schedule triggers
    actions: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    last_triggered: str = ""
    cooldown_seconds: int = 300  # Minimum time between triggers


class AutomationEngine:
    """
    Background automation engine.

    Listens to events and runs periodic checks to trigger automation rules.
    """

    def __init__(self, event_bus: EventBus, settings):
        self.event_bus = event_bus
        self.settings = settings
        self.rules: list[AutomationRule] = []
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

        # Register built-in rules
        self._register_builtin_rules()

    def _register_builtin_rules(self):
        """Register default automation rules."""

        # Rule: Notify when a new device appears
        self.rules.append(
            AutomationRule(
                name="new_device_alert",
                description="Notify when a new device is discovered on the network.",
                trigger_type="event",
                trigger_event=EventType.NETWORK_DEVICE_DISCOVERED,
                actions=[
                    {
                        "type": "notification",
                        "message": "New device discovered on the network: {friendly_name} ({ip})",
                    }
                ],
            )
        )

        # Rule: Auto-deactivate scene when TV goes offline
        self.rules.append(
            AutomationRule(
                name="scene_auto_deactivate",
                description="Deactivate active scene when the TV goes offline.",
                trigger_type="event",
                trigger_event=EventType.DEVICE_OFFLINE,
                actions=[
                    {"type": "scene_deactivate"},
                ],
                cooldown_seconds=60,
            )
        )

        # Rule: Late-night volume check (after 11 PM)
        self.rules.append(
            AutomationRule(
                name="late_night_volume",
                description="Remind user to lower volume after 11 PM.",
                trigger_type="schedule",
                schedule_hour=23,
                actions=[
                    {
                        "type": "notification",
                        "message": "It's getting late, sir. Consider lowering the volume or activating Sleep Mode.",
                    }
                ],
                cooldown_seconds=3600,  # Once per hour max
            )
        )

    async def start(self):
        """Start the automation engine."""
        self._running = True
        logger.info("automation_engine_starting", rules=len(self.rules))

        # Subscribe to all events for reactive rules
        self.event_bus.subscribe_all(self._on_event)

        # Start heartbeat for scheduled rules
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("automation_engine_started")

    async def stop(self):
        """Stop the automation engine."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("automation_engine_stopped")

    async def _on_event(self, event: Event):
        """Handle incoming events and check against rules."""
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.trigger_type != "event":
                continue
            if rule.trigger_event != event.type:
                continue

            # Check cooldown
            if rule.last_triggered:
                from datetime import datetime as dt
                last = dt.fromisoformat(rule.last_triggered)
                now = dt.now(timezone.utc)
                if (now - last).total_seconds() < rule.cooldown_seconds:
                    continue

            await self._execute_rule(rule, event.data)

    async def _heartbeat_loop(self):
        """Periodic check for schedule-based rules."""
        while self._running:
            await asyncio.sleep(60)  # Check every minute

            now = datetime.now(timezone.utc)
            current_hour = now.hour

            for rule in self.rules:
                if not rule.enabled:
                    continue
                if rule.trigger_type != "schedule":
                    continue
                if rule.schedule_hour is None or rule.schedule_hour != current_hour:
                    continue

                # Check cooldown
                if rule.last_triggered:
                    last = datetime.fromisoformat(rule.last_triggered)
                    if (now - last).total_seconds() < rule.cooldown_seconds:
                        continue

                await self._execute_rule(rule, {})

    async def _execute_rule(self, rule: AutomationRule, context: dict):
        """Execute the actions of a triggered rule."""
        rule.last_triggered = datetime.now(timezone.utc).isoformat()
        logger.info("automation_rule_triggered", rule=rule.name)

        for action in rule.actions:
            action_type = action.get("type")

            if action_type == "notification":
                msg = action.get("message", "")
                # Format with context data
                try:
                    msg = msg.format(**context)
                except (KeyError, IndexError):
                    pass

                await self.event_bus.emit(
                    Event(
                        type=EventType.SYSTEM_NOTIFICATION,
                        data={"message": msg, "source": f"automation:{rule.name}"},
                    )
                )

            elif action_type == "scene_deactivate":
                try:
                    from core.dependencies import get_container
                    container = get_container()
                    sm = container.scene_manager()
                    if sm.active_scene:
                        await sm.deactivate_scene()
                except Exception as e:
                    logger.warning("automation_scene_deactivate_failed", error=str(e))

            elif action_type == "chromecast":
                try:
                    from core.dependencies import get_container
                    container = get_container()
                    registry = container.tool_registry()
                    tool = registry.get_tool("chromecast")
                    if tool:
                        await tool.execute(**action.get("params", {}))
                except Exception as e:
                    logger.warning("automation_chromecast_failed", error=str(e))
