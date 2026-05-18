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

    async def initialize(self) -> None:
        """Pre-initialize critical services."""
        logger.info("container_initializing")
        memory = self.memory_manager()
        await memory.initialize()
        self.tool_registry()  # Register all tools
        logger.info("container_ready")

    async def shutdown(self) -> None:
        """Cleanup all services."""
        logger.info("container_shutdown")
        memory = self._instances.get("memory_manager")
        if memory and hasattr(memory, "close"):
            await memory.close()


# Singleton
_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container(get_settings())
    return _container
