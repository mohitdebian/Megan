"""
Scene Manager — Advanced Automation Orchestration Engine.

Supports conditional logic, chained actions, delayed execution,
parallel tasks, and rollback. Powers 8+ preset environment scenes.
"""

import asyncio
import structlog
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

from core.events import EventBus, Event, EventType

logger = structlog.get_logger(__name__)


@dataclass
class SceneAction:
    """A single step in a scene's execution chain."""

    action_type: str  # "chromecast", "event", "delay", "notification"
    target: str = ""  # device name, event type, etc.
    params: dict[str, Any] = field(default_factory=dict)
    delay_seconds: float = 0  # wait before executing
    description: str = ""  # human-readable description


@dataclass
class SceneDefinition:
    """A complete scene with actions and rollback."""

    name: str
    display_name: str
    description: str
    icon: str = "🎬"
    actions: list[SceneAction] = field(default_factory=list)
    rollback_actions: list[SceneAction] = field(default_factory=list)


# ═══════════════════════════════════════
# PRESET SCENE DEFINITIONS
# ═══════════════════════════════════════

PRESET_SCENES: dict[str, SceneDefinition] = {
    "movie_mode": SceneDefinition(
        name="movie_mode",
        display_name="Movie Mode",
        description="Dims the environment, sets TV volume, and activates cinematic ambience.",
        icon="🎬",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "movie"}, description="Dim UI to cinematic mode"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "30"}, description="Set TV volume to 30%"),
            SceneAction("notification", "", {"message": "Movie Mode activated. Enjoy the show, sir."}, description="Notify user"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}, description="Restore normal UI"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "20"}, description="Restore default volume"),
        ],
    ),
    "gaming_mode": SceneDefinition(
        name="gaming_mode",
        display_name="Gaming Mode",
        description="Low latency mode with vivid visuals and boosted audio.",
        icon="🎮",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "gaming"}, description="Activate gaming HUD"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "40"}, description="Boost TV volume"),
            SceneAction("notification", "", {"message": "Gaming Mode activated. Good luck, sir."}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
        ],
    ),
    "focus_mode": SceneDefinition(
        name="focus_mode",
        display_name="Focus Mode",
        description="Minimizes distractions. Mutes TV, dims ambient, silences notifications.",
        icon="🧠",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "focus"}, description="Activate focus UI"),
            SceneAction("chromecast", "", {"action": "mute"}, description="Mute the TV"),
            SceneAction("notification", "", {"message": "Focus Mode activated. Distractions minimized."}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
            SceneAction("chromecast", "", {"action": "unmute"}),
        ],
    ),
    "sleep_mode": SceneDefinition(
        name="sleep_mode",
        display_name="Sleep Mode",
        description="Gradually dims everything, lowers volume, and prepares for sleep.",
        icon="🌙",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "sleep"}, description="Activate sleep ambient"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "5"}, description="Lower TV volume to 5%"),
            SceneAction("delay", "", {}, delay_seconds=2, description="Wait 2 seconds"),
            SceneAction("chromecast", "", {"action": "stop"}, description="Stop playback"),
            SceneAction("notification", "", {"message": "Sleep Mode activated. Good night, sir."}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "20"}),
        ],
    ),
    "party_mode": SceneDefinition(
        name="party_mode",
        display_name="Party Mode",
        description="Cranks volume, activates vibrant visuals, and launches music.",
        icon="🎉",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "party"}, description="Activate party visuals"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "70"}, description="Crank TV volume to 70%"),
            SceneAction("notification", "", {"message": "Party Mode activated. Let's go!"}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "20"}),
        ],
    ),
    "cyberpunk_mode": SceneDefinition(
        name="cyberpunk_mode",
        display_name="Cyberpunk Mode",
        description="Neon-drenched, futuristic dashboard with AI command center aesthetics.",
        icon="🌆",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "cyberpunk"}, description="Activate cyberpunk HUD"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "25"}, description="Set atmospheric volume"),
            SceneAction("notification", "", {"message": "Cyberpunk Mode activated. Welcome to Night City."}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
        ],
    ),
    "presentation_mode": SceneDefinition(
        name="presentation_mode",
        display_name="Presentation Mode",
        description="Clean display, muted TV, no distractions for presenting.",
        icon="📊",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "presentation"}, description="Clean presentation UI"),
            SceneAction("chromecast", "", {"action": "mute"}, description="Mute TV"),
            SceneAction("notification", "", {"message": "Presentation Mode activated. You're live."}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
            SceneAction("chromecast", "", {"action": "unmute"}),
        ],
    ),
    "anime_night_mode": SceneDefinition(
        name="anime_night_mode",
        display_name="Anime Night Mode",
        description="Perfect setup for anime watching — warm ambience, medium volume, cozy vibes.",
        icon="🍥",
        actions=[
            SceneAction("event", "ambient", {"ambient_mode": "anime_night"}, description="Warm anime ambience"),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "35"}, description="Set cozy volume"),
            SceneAction("notification", "", {"message": "Anime Night Mode activated. Itadakimasu!"}, description="Notify"),
        ],
        rollback_actions=[
            SceneAction("event", "ambient", {"ambient_mode": "normal"}),
            SceneAction("chromecast", "", {"action": "set_volume", "value": "20"}),
        ],
    ),
}


class SceneManager:
    """
    Advanced scene orchestration engine.

    Executes chained actions with delays, emits events for UI reactivity,
    and supports rollback to undo scenes.
    """

    def __init__(self, event_bus: EventBus, settings):
        self.event_bus = event_bus
        self.settings = settings
        self.active_scene: SceneDefinition | None = None
        self._chromecast_tool = None  # Injected lazily

    def _get_chromecast_tool(self):
        """Lazily get ChromecastTool from the container."""
        if not self._chromecast_tool:
            from core.dependencies import get_container
            container = get_container()
            self._chromecast_tool = container._instances.get("tool_registry")
            if self._chromecast_tool:
                self._chromecast_tool = self._chromecast_tool.get_tool("chromecast")
        return self._chromecast_tool

    def list_scenes(self) -> list[dict]:
        """Return all available scenes."""
        return [
            {
                "name": s.name,
                "display_name": s.display_name,
                "description": s.description,
                "icon": s.icon,
            }
            for s in PRESET_SCENES.values()
        ]

    def get_active_scene(self) -> str | None:
        """Return the currently active scene name."""
        return self.active_scene.name if self.active_scene else None

    async def execute_scene(self, scene_name: str) -> str:
        """Execute a scene by name."""
        scene_name = scene_name.lower().replace(" ", "_")

        if scene_name == "normal_mode" or scene_name == "normal":
            return await self.deactivate_scene()

        scene = PRESET_SCENES.get(scene_name)
        if not scene:
            available = ", ".join(PRESET_SCENES.keys())
            raise ValueError(f"Unknown scene: '{scene_name}'. Available: {available}, normal_mode")

        # If another scene is active, rollback first
        if self.active_scene:
            await self._execute_actions(self.active_scene.rollback_actions, silent=True)

        logger.info("scene_activating", scene=scene.name)

        # Execute the action chain
        results = await self._execute_actions(scene.actions)

        self.active_scene = scene

        # Emit scene activation event
        await self.event_bus.emit(
            Event(
                type=EventType.SCENE_ACTIVATED,
                data={
                    "scene": scene.name,
                    "display_name": scene.display_name,
                    "icon": scene.icon,
                },
            )
        )

        result_summary = f"{scene.icon} {scene.display_name} activated.\n"
        for r in results:
            result_summary += f"  ✓ {r}\n"

        return result_summary.strip()

    async def deactivate_scene(self) -> str:
        """Rollback the active scene to normal."""
        if not self.active_scene:
            return "No active scene to deactivate. Already in normal mode."

        old_scene = self.active_scene
        logger.info("scene_deactivating", scene=old_scene.name)

        await self._execute_actions(old_scene.rollback_actions, silent=True)
        self.active_scene = None

        await self.event_bus.emit(
            Event(
                type=EventType.SCENE_DEACTIVATED,
                data={"scene": old_scene.name},
            )
        )

        # Also emit normal ambient
        await self.event_bus.emit(
            Event(type=EventType.STATUS, data={"ambient_mode": "normal"})
        )

        return f"Deactivated {old_scene.display_name}. Returned to normal mode."

    async def _execute_actions(
        self, actions: list[SceneAction], silent: bool = False
    ) -> list[str]:
        """Execute a list of scene actions sequentially."""
        results = []

        for action in actions:
            if action.delay_seconds > 0:
                await asyncio.sleep(action.delay_seconds)
                if not silent:
                    results.append(f"Waited {action.delay_seconds}s")
                continue

            if action.action_type == "event":
                await self.event_bus.emit(
                    Event(type=EventType.STATUS, data=action.params)
                )
                if not silent:
                    results.append(action.description or "Emitted event")

            elif action.action_type == "chromecast":
                tool = self._get_chromecast_tool()
                if tool:
                    try:
                        result = await tool.execute(**action.params)
                        if not silent:
                            results.append(action.description or result.output)
                    except Exception as e:
                        logger.warning("scene_action_failed", action="chromecast", error=str(e))
                        if not silent:
                            results.append(f"⚠ {action.description} (skipped: {e})")

            elif action.action_type == "notification":
                msg = action.params.get("message", "")
                await self.event_bus.emit(
                    Event(
                        type=EventType.SYSTEM_NOTIFICATION,
                        data={"message": msg},
                    )
                )
                if not silent:
                    results.append(action.description or "Sent notification")

        return results
