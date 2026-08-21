from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_path: Path = Path("./data/batch-copy-qc.sqlite3")
    upload_dir: Path = Path("./data/uploads")
    frontend_dist_dir: Path = Path("./frontend/dist")
    model_adapter: str = "fake"
    cliproxy_base_url: str = ""
    cliproxy_api_key: str = ""
    cliproxy_generation_model: str = ""
    cliproxy_qc_model: str = ""
    cliproxy_reasoning_effort: str = "medium"
    cliproxy_api_mode: Literal["responses", "auto", "chat"] = "responses"
    cliproxy_timeout_seconds: float = 120
    model_concurrency: int = Field(2, ge=1, le=20)
    auto_rewrite_limit: int = Field(4, ge=0, le=10)
    api_retry_limit: int = Field(2, ge=0, le=10)
    similarity_threshold: int = Field(85, ge=0, le=100)
    qc_confidence_threshold: float = Field(0.70, ge=0, le=1)
    feishu_adapter: str = "fake"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_spreadsheet_token: str = ""
    feishu_wiki_node_token: str = ""
    feishu_base_url: str = "https://open.feishu.cn"

    @property
    def model_configured(self) -> bool:
        if self.model_adapter == "fake":
            return True
        return self.model_adapter == "cliproxy" and all(
            (
                self.cliproxy_base_url,
                self.cliproxy_api_key,
                self.cliproxy_generation_model,
                self.cliproxy_qc_model,
            )
        )

    @property
    def feishu_configured(self) -> bool:
        if self.feishu_adapter == "fake":
            return True
        return self.feishu_adapter == "feishu" and bool(
            self.feishu_app_id
            and self.feishu_app_secret
            and (self.feishu_spreadsheet_token or self.feishu_wiki_node_token)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
