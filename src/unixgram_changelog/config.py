from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(min_length=20)
    channel_id: str = "@UnixGramChangelog"
    admin_ids: frozenset[int]
    database_path: Path = Path("data/changelog.db")
    log_level: str = "INFO"
    review_required: bool = True

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> object:
        if isinstance(value, int):
            return frozenset((value,))
        if isinstance(value, str):
            return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def require_single_owner(self) -> Settings:
        if len(self.admin_ids) != 1:
            raise ValueError("ADMIN_IDS must contain exactly one owner id")
        return self

    @property
    def owner_id(self) -> int:
        return next(iter(self.admin_ids))
