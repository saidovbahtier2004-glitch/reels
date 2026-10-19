"""Settings are read only from environment variables (never hardcoded)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} butun son bo'lishi kerak / must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    bot_token: str
    recognition_provider: str = "none"  # audd | acrcloud | none
    audd_api_token: str = ""
    acrcloud_host: str = ""
    acrcloud_access_key: str = ""
    acrcloud_access_secret: str = ""
    max_upload_mb: int = 49  # Telegram Bot API upload limit is 50 MB
    max_parallel_jobs: int = 3
    itunes_country: str = "US"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def recognition_ready(self) -> bool:
        if self.recognition_provider == "audd":
            return bool(self.audd_api_token)
        if self.recognition_provider == "acrcloud":
            return bool(self.acrcloud_host and self.acrcloud_access_key and self.acrcloud_access_secret)
        return False


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    token = env.get("BOT_TOKEN", "").strip()
    if not token or ":" not in token:
        raise ConfigError(
            "BOT_TOKEN topilmadi. .env faylida yoki hosting 'Environment variables' bo'limida BOT_TOKEN ni kiriting."
        )
    provider = env.get("RECOGNITION_PROVIDER", "none").strip().lower() or "none"
    if provider not in {"audd", "acrcloud", "none"}:
        raise ConfigError("RECOGNITION_PROVIDER: audd, acrcloud yoki none bo'lishi kerak")
    return Settings(
        bot_token=token,
        recognition_provider=provider,
        audd_api_token=env.get("AUDD_API_TOKEN", "").strip(),
        acrcloud_host=env.get("ACRCLOUD_HOST", "").strip(),
        acrcloud_access_key=env.get("ACRCLOUD_ACCESS_KEY", "").strip(),
        acrcloud_access_secret=env.get("ACRCLOUD_ACCESS_SECRET", "").strip(),
        max_upload_mb=min(_int(env, "MAX_UPLOAD_MB", 49), 50),
        max_parallel_jobs=max(1, _int(env, "MAX_PARALLEL_JOBS", 3)),
        itunes_country=env.get("ITUNES_COUNTRY", "US").strip().upper() or "US",
    )
