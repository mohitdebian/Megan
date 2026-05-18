"""
Dependency Injection Container — lazy-initialized singleton services.

All heavy services (memory, tools, audio) are created once and shared.
"""

import structlog
from config import get_settings, Settings

logger = structlog.get_logger(__name__)


class Container:
    """
    Simple DI container. Services are lazily created on first access.

    Usage:
        container = get_container()
        memory = await container.memory_manager()
        tools = container.tool_registry()
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._instances: dict[str, object] = {}

    def _get_or_create(self, key: str, factory):
        if key not in self._instances:
            self._instances[key] = factory()
            logger.info("service_created", service=key)
        return self._instances[key]

    def tool_registry(self):
        from tools.registry import ToolRegistry

        def factory():
            from tools.terminal import TerminalTool
            from tools.filesystem import FileSystemTool
            from tools.web_search import WebSearchTool
            from tools.browser import BrowserTool
            from tools.code_executor import CodeExecutorTool
            from tools.clipboard import ClipboardTool
            from tools.app_launcher import AppLauncherTool
            from tools.system_info import SystemInfoTool
            from tools.codebase import CodebaseTool
            from tools.email import EmailTool
            from tools.whatsapp import WhatsAppTool
            from tools.background_worker import BackgroundWorkerTool, CheckBackgroundTasksTool
            from tools.persona_tool import PersonaTool
            from tools.telegram import TelegramTool
            from tools.reminder import ReminderTool
            from tools.window import WindowTool
            from tools.screen_vision import ScreenVisionTool
            from tools.chromecast import ChromecastTool
            from tools.scene_tool import SceneTool
            from tools.network import NetworkIntelligenceTool
            from tools.media_tool import MediaTool
            from tools.security_tool import SecurityTool
            from tools.youtube import YouTubeTool

            registry = ToolRegistry()
            registry.register(TerminalTool(self.settings))
            registry.register(FileSystemTool(self.settings))
            registry.register(WebSearchTool(self.settings))
            registry.register(BrowserTool(self.settings))
            registry.register(CodeExecutorTool(self.settings))
            registry.register(ClipboardTool(self.settings))
            registry.register(AppLauncherTool(self.settings))
            registry.register(SystemInfoTool(self.settings))
            registry.register(CodebaseTool(self.settings))
            registry.register(EmailTool())
            registry.register(WhatsAppTool(self.settings, self.memory_manager()))
            registry.register(BackgroundWorkerTool(self))
            registry.register(CheckBackgroundTasksTool(self))
            registry.register(PersonaTool(self.memory_manager()))
            registry.register(ScreenVisionTool(self.settings))
            registry.register(ChromecastTool(self.settings, self.device_manager()))
            registry.register(SceneTool(self.scene_manager()))
            registry.register(NetworkIntelligenceTool(self.device_manager()))
            registry.register(MediaTool(self.media_library()))
            registry.register(SecurityTool(self.network_intelligence()))
            registry.register(YouTubeTool())

            telegram_tool = TelegramTool(self.settings)
            registry.register(telegram_tool)
            registry.register(ReminderTool(telegram_tool))
            registry.register(WindowTool())
            return registry

        return self._get_or_create("tool_registry", factory)

    def memory_manager(self):
        from memory.manager import MemoryManager

        def factory():
            return MemoryManager(self.settings)

        return self._get_or_create("memory_manager", factory)

    def event_bus(self):
        from core.events import get_event_bus

        return get_event_bus()

    def new_agent_brain(self):
        """Return a fresh AgentBrain instance (useful for background tasks)."""
        from agent.brain import AgentBrain
        return AgentBrain(
            settings=self.settings,
            tool_registry=self.tool_registry(),
            memory_manager=self.memory_manager(),
            event_bus=self.event_bus(),
        )

    def agent_brain(self):
        """Return the singleton AgentBrain instance for the main thread."""
        return self._get_or_create("agent_brain", self.new_agent_brain)

    def tts_service(self):
        from audio.tts_service import TTSService

        def factory():
            return TTSService(self.settings)

        return self._get_or_create("tts_service", factory)

    def stt_service(self):
        from audio.stt_service import STTService

        def factory():
            return STTService(self.settings)

        return self._get_or_create("stt_service", factory)

    def stream_manager(self):
        from audio.stream_manager import StreamManager

        def factory():
            return StreamManager(
                tts=self.tts_service(),
                stt=self.stt_service(),
                event_bus=self.event_bus(),
            )

        return self._get_or_create("stream_manager", factory)

    def device_manager(self):
        from services.device_manager import DeviceManager

        def factory():
            return DeviceManager(self.event_bus(), self.settings.data_dir)

        return self._get_or_create("device_manager", factory)

    def lan_monitor(self):
        from services.lan_monitor import LANMonitor

        def factory():
            return LANMonitor(self.event_bus(), self.device_manager())

        return self._get_or_create("lan_monitor", factory)

    def scene_manager(self):
        from services.scene_manager import SceneManager

        def factory():
            return SceneManager(self.event_bus(), self.settings)

        return self._get_or_create("scene_manager", factory)

    def automation_engine(self):
        from services.automation_engine import AutomationEngine

        def factory():
            return AutomationEngine(self.event_bus(), self.settings)

        return self._get_or_create("automation_engine", factory)

    def media_library(self):
        from services.media_library import MediaLibrary

        def factory():
            return MediaLibrary(self.settings.data_dir)

        return self._get_or_create("media_library", factory)

    def network_intelligence(self):
        from services.network_intelligence import NetworkIntelligence

        def factory():
            return NetworkIntelligence(self.event_bus(), self.settings.data_dir)

        return self._get_or_create("network_intelligence", factory)

    def heartbeat(self):
        from services.heartbeat import SystemHeartbeat

        def factory():
            return SystemHeartbeat(self.event_bus(), self)

        return self._get_or_create("heartbeat", factory)

    async def initialize(self) -> None:
        """Pre-initialize critical services."""
        logger.info("container_initializing")
        memory = self.memory_manager()
        await memory.initialize()
        self.tool_registry()  # Register all tools

        # Start LAN discovery & device health monitoring
        monitor = self.lan_monitor()
        await monitor.start()
        dm = self.device_manager()
        await dm.start_health_monitor()

        # Start automation engine
        engine = self.automation_engine()
        await engine.start()

        # Initialize media library scan
        ml = self.media_library()
        import asyncio
        asyncio.create_task(ml.scan())
        
        # Start network intelligence scanning
        ni = self.network_intelligence()
        await ni.start_periodic_scan()
        
        # Start heartbeat
        hb = self.heartbeat()
        await hb.start()

        logger.info("container_ready")

    async def shutdown(self) -> None:
        """Cleanup all services."""
        logger.info("container_shutdown")
        
        hb = self._instances.get("heartbeat")
        if hb and hasattr(hb, "stop"):
            await hb.stop()

        ni = self._instances.get("network_intelligence")
        if ni and hasattr(ni, "stop_periodic_scan"):
            await ni.stop_periodic_scan()

        engine = self._instances.get("automation_engine")
        if engine and hasattr(engine, "stop"):
            await engine.stop()

        memory = self._instances.get("memory_manager")
        if memory and hasattr(memory, "close"):
            await memory.close()

        dm = self._instances.get("device_manager")
        if dm and hasattr(dm, "stop_health_monitor"):
            await dm.stop_health_monitor()

        lan = self._instances.get("lan_monitor")
        if lan and hasattr(lan, "stop"):
            await lan.stop()


# Singleton
_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container(get_settings())
    return _container
