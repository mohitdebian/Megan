"""
Megan Configuration — Pydantic Settings with .env support.
All config is centralized here. No magic strings in the codebase.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


from dotenv import load_dotenv

load_dotenv("../.env")

class ClaudeSettings(BaseSettings):
    base_url: str = Field("http://localhost:8082", alias="CLAUDE_BASE_URL")
    auth_token: str = Field("freecc", alias="CLAUDE_AUTH_TOKEN")
    model: str = Field(
        "anthropic/nvidia_nim/moonshotai/kimi-k2-thinking",
        alias="CLAUDE_MODEL",
    )
    max_tokens: int = Field(8192, alias="CLAUDE_MAX_TOKENS")
    max_agent_iterations: int = Field(25, alias="CLAUDE_MAX_ITERATIONS")


class NvidiaTTSSettings(BaseSettings):
    api_key: str = Field("", alias="NVIDIA_API_KEY")
    url: str = Field(
        "https://integrate.api.nvidia.com/v1/audio/speech",
        alias="NVIDIA_TTS_URL",
    )
    voice: str = Field("magpie-multilingual", alias="NVIDIA_TTS_VOICE")
    sample_rate: int = Field(24000, alias="NVIDIA_TTS_SAMPLE_RATE")


class AudioSettings(BaseSettings):
    stt_model: str = Field("base", alias="STT_MODEL")
    stt_device: str = Field("cuda", alias="STT_DEVICE")
    sample_rate: int = Field(16000, alias="AUDIO_SAMPLE_RATE")
    chunk_duration_ms: int = Field(100, alias="AUDIO_CHUNK_MS")


class MemorySettings(BaseSettings):
    sqlite_path: str = Field("./data/memory.db", alias="SQLITE_PATH")
    chroma_path: str = Field("./data/chroma", alias="CHROMA_PATH")
    short_term_max_messages: int = Field(50, alias="SHORT_TERM_MAX")
    embedding_model: str = Field(
        "all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )


class SafetySettings(BaseSettings):
    require_confirmation: bool = Field(True, alias="REQUIRE_CONFIRMATION")
    allowed_dirs: str = Field("/home", alias="ALLOWED_DIRS")
    command_timeout: int = Field(30, alias="COMMAND_TIMEOUT")
    code_timeout: int = Field(30, alias="CODE_TIMEOUT")
    home_dir: str = Field("/home/mohit", alias="HOME_DIR")


class ServerSettings(BaseSettings):
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")
    log_level: str = Field("info", alias="LOG_LEVEL")
    cors_origins: list[str] = Field(
        ["http://localhost:5173", "http://localhost:3000", "http://172.16.8.139:5173", "http://172.16.8.139:8000"],
        alias="CORS_ORIGINS",
    )


class EmailSettings(BaseSettings):
    imap_server: str = Field("imap.gmail.com", alias="IMAP_SERVER")
    smtp_server: str = Field("smtp.gmail.com", alias="SMTP_SERVER")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    email_address: str = Field("", alias="EMAIL_ADDRESS")
    app_password: str = Field("", alias="EMAIL_APP_PASSWORD")


class ElevenLabsSettings(BaseSettings):
    api_key: str = Field("", alias="ELEVENLABS_API_KEY")
    voice_id: str = Field("JBFqnCBsd6RMkjVDRZzb", alias="ELEVENLABS_VOICE_ID")
    model_id: str = Field("eleven_v3", alias="ELEVENLABS_MODEL_ID")
    output_format: str = Field("mp3_44100_128", alias="ELEVENLABS_OUTPUT_FORMAT")


class WhatsAppSettings(BaseSettings):
    bridge_url: str = Field("http://localhost:3001", alias="WHATSAPP_BRIDGE_URL")


class TelegramSettings(BaseSettings):
    bot_token: str = Field("", alias="TELEGRAM_BOT_TOKEN")
    chat_id: str = Field("", alias="TELEGRAM_CHAT_ID")


class Settings(BaseSettings):
    """Root settings — aggregates all sub-settings."""

    claude: ClaudeSettings = ClaudeSettings()
    tts: NvidiaTTSSettings = NvidiaTTSSettings()
    audio: AudioSettings = AudioSettings()
    memory: MemorySettings = MemorySettings()
    safety: SafetySettings = SafetySettings()
    server: ServerSettings = ServerSettings()
    email: EmailSettings = EmailSettings()
    elevenlabs: ElevenLabsSettings = ElevenLabsSettings()
    whatsapp: WhatsAppSettings = WhatsAppSettings()
    telegram: TelegramSettings = TelegramSettings()

    # Resolved paths
    @property
    def data_dir(self) -> Path:
        path = Path("./data")
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
