from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ASRProvider = Literal["doubao", "openai_whisper", "deepgram", "qwen"]
LLMProvider = Literal["deepseek", "qwen", "anthropic"]
TTSProvider = Literal["doubao", "qwen"]


def _present(value: SecretStr | str | Path | int | None) -> bool:
    if value is None:
        return False
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value().strip())
    return bool(str(value).strip())


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        case_sensitive=True,
        extra="ignore",
    )

    DATA_DIR: Path = Path("data")
    DB_PATH: Path = Path("data/podsum.sqlite3")
    MAX_CONCURRENCY: int = Field(default=2, ge=1, le=8)
    LOG_LEVEL: str = "INFO"

    ASR_PROVIDER: ASRProvider = "doubao"
    LLM_PROVIDER: LLMProvider = "deepseek"
    TTS_PROVIDER: TTSProvider = "doubao"

    VOLC_ACCESS_KEY_ID: SecretStr | None = None
    VOLC_SECRET_ACCESS_KEY: SecretStr | None = None

    DOUBAO_ASR_APP_ID: str | None = None
    DOUBAO_ASR_ACCESS_TOKEN: SecretStr | None = None
    DOUBAO_ASR_CLUSTER: str = "volcengine_streaming_common"
    DOUBAO_ASR_RESOURCE_ID: str = "volc.seedasr.auc"
    DOUBAO_ASR_SUBMIT_URL: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
    DOUBAO_ASR_QUERY_URL: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
    DOUBAO_ASR_FLASH_RESOURCE_ID: str = "volc.bigasr.auc_turbo"
    DOUBAO_ASR_FLASH_URL: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    DOUBAO_ASR_POLL_INTERVAL_SECONDS: float = Field(default=3.0, ge=0.2, le=30.0)
    DOUBAO_ASR_TIMEOUT_SECONDS: float = Field(default=1800.0, ge=30.0, le=21600.0)

    DEEPSEEK_API_KEY: SecretStr | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    QWEN_LLM_MODEL: str = "qwen-max"
    ANTHROPIC_MODEL: str | None = None

    DOUBAO_TTS_APP_ID: str | None = None
    DOUBAO_TTS_ACCESS_TOKEN: SecretStr | None = None
    DOUBAO_TTS_VOICE_TYPE_ZH: str = "BV700_streaming"
    DOUBAO_TTS_VOICE_TYPE_EN: str = "BV701_streaming"
    DOUBAO_TTS_CLUSTER: str = "volcano_tts"
    QWEN_TTS_MODEL: str = "cosyvoice-v2"
    QWEN_TTS_VOICE: str = "longxiaochun"

    OPENAI_API_KEY: SecretStr | None = None
    DEEPGRAM_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    DASHSCOPE_API_KEY: SecretStr | None = None

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.DB_PATH}"

    @model_validator(mode="after")
    def validate_provider_keys(self) -> Settings:
        missing: list[str] = []

        if self.ASR_PROVIDER == "doubao":
            missing.extend(
                key
                for key, value in (
                    ("VOLC_ACCESS_KEY_ID", self.VOLC_ACCESS_KEY_ID),
                    ("VOLC_SECRET_ACCESS_KEY", self.VOLC_SECRET_ACCESS_KEY),
                    ("DOUBAO_ASR_APP_ID", self.DOUBAO_ASR_APP_ID),
                    ("DOUBAO_ASR_ACCESS_TOKEN", self.DOUBAO_ASR_ACCESS_TOKEN),
                    ("DOUBAO_ASR_RESOURCE_ID", self.DOUBAO_ASR_RESOURCE_ID),
                    ("DOUBAO_ASR_SUBMIT_URL", self.DOUBAO_ASR_SUBMIT_URL),
                    ("DOUBAO_ASR_QUERY_URL", self.DOUBAO_ASR_QUERY_URL),
                    ("DOUBAO_ASR_FLASH_RESOURCE_ID", self.DOUBAO_ASR_FLASH_RESOURCE_ID),
                    ("DOUBAO_ASR_FLASH_URL", self.DOUBAO_ASR_FLASH_URL),
                )
                if not _present(value)
            )
        elif self.ASR_PROVIDER == "openai_whisper" and not _present(self.OPENAI_API_KEY):
            missing.append("OPENAI_API_KEY")
        elif self.ASR_PROVIDER == "deepgram" and not _present(self.DEEPGRAM_API_KEY):
            missing.append("DEEPGRAM_API_KEY")
        elif self.ASR_PROVIDER == "qwen" and not _present(self.DASHSCOPE_API_KEY):
            missing.append("DASHSCOPE_API_KEY")

        if self.LLM_PROVIDER == "deepseek":
            missing.extend(
                key
                for key, value in (
                    ("DEEPSEEK_API_KEY", self.DEEPSEEK_API_KEY),
                    ("DEEPSEEK_BASE_URL", self.DEEPSEEK_BASE_URL),
                    ("DEEPSEEK_MODEL", self.DEEPSEEK_MODEL),
                )
                if not _present(value)
            )
        elif self.LLM_PROVIDER == "qwen":
            missing.extend(
                key
                for key, value in (
                    ("DASHSCOPE_API_KEY", self.DASHSCOPE_API_KEY),
                    ("QWEN_LLM_MODEL", self.QWEN_LLM_MODEL),
                )
                if not _present(value)
            )
        elif self.LLM_PROVIDER == "anthropic":
            missing.extend(
                key
                for key, value in (
                    ("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY),
                    ("ANTHROPIC_MODEL", self.ANTHROPIC_MODEL),
                )
                if not _present(value)
            )

        if self.TTS_PROVIDER == "doubao":
            missing.extend(
                key
                for key, value in (
                    ("VOLC_ACCESS_KEY_ID", self.VOLC_ACCESS_KEY_ID),
                    ("VOLC_SECRET_ACCESS_KEY", self.VOLC_SECRET_ACCESS_KEY),
                    ("DOUBAO_TTS_APP_ID", self.DOUBAO_TTS_APP_ID),
                    ("DOUBAO_TTS_ACCESS_TOKEN", self.DOUBAO_TTS_ACCESS_TOKEN),
                    ("DOUBAO_TTS_VOICE_TYPE_ZH", self.DOUBAO_TTS_VOICE_TYPE_ZH),
                    ("DOUBAO_TTS_VOICE_TYPE_EN", self.DOUBAO_TTS_VOICE_TYPE_EN),
                    ("DOUBAO_TTS_CLUSTER", self.DOUBAO_TTS_CLUSTER),
                )
                if not _present(value)
            )
        elif self.TTS_PROVIDER == "qwen" and not _present(self.DASHSCOPE_API_KEY):
            missing.append("DASHSCOPE_API_KEY")

        if missing:
            unique = ", ".join(sorted(set(missing)))
            raise ValueError(f"missing required provider configuration: {unique}")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
