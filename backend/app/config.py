from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_GITHUB_API_HOSTS = {"api.github.com"}
ALLOWED_GITHUB_WEB_HOSTS = {"github.com", "www.github.com"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    github_token: str = ""
    github_api_base: str = "https://api.github.com"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_files: int = 80
    max_file_bytes: int = 120_000
    max_total_chars: int = 250_000
    max_tree_items: int = 5_000
    max_chunks: int = 1_200
    chunk_lines: int = 80
    chunk_overlap: int = 12
    request_timeout_seconds: float = 25.0
    connect_timeout_seconds: float = 8.0
    github_concurrency: int = 5
    database_path: str = "./data/repomind.db"
    chat_history_limit: int = 8
    analyze_rate_limit: int = 20
    analyze_rate_window_seconds: int = 600
    chat_rate_limit: int = 60
    chat_rate_window_seconds: int = 60
    log_level: str = "INFO"

    @field_validator("github_api_base")
    @classmethod
    def validate_github_api_base(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_GITHUB_API_HOSTS:
            raise ValueError("GITHUB_API_BASE must be https://api.github.com")
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url.strip() and self.llm_api_key.strip() and self.llm_model.strip())

    @property
    def embeddings_configured(self) -> bool:
        key = self.embedding_api_key.strip() or self.llm_api_key.strip()
        base = self.embedding_base_url.strip() or self.llm_base_url.strip()
        model = self.embedding_model.strip()
        return bool(base and key and model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
