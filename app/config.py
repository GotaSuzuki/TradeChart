"""設定値を一元管理するモジュール。"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    company_name: str = "Gota Suzuki"
    email_address: str = "go.baseball.0408@icloud.com"
    filings_years: int = 5
    cache_ttl_hours: int = 12
    download_dir: str = "data/raw"
    line_channel_access_token: Optional[str] = None
    line_channel_secret: Optional[str] = None
    line_target_user_id: Optional[str] = None
    rsi_alert_threshold: float = 40.0

    @property
    def user_agent(self) -> str:
        return f"{self.company_name} {self.email_address}"


def get_config() -> AppConfig:
    defaults = AppConfig()
    return AppConfig(
        company_name=os.getenv("APP_COMPANY_NAME", defaults.company_name),
        email_address=os.getenv("APP_EMAIL_ADDRESS", defaults.email_address),
        filings_years=_int_env("APP_FILINGS_YEARS", defaults.filings_years),
        cache_ttl_hours=_int_env("APP_CACHE_TTL_HOURS", defaults.cache_ttl_hours),
        download_dir=os.getenv("APP_DOWNLOAD_DIR", defaults.download_dir),
        line_channel_access_token=_clean_secret(
            _env_first(
                ["LINE_CHANNEL_ACCESS_TOKEN", "CHANNEL_ACCESS_TOKEN"],
                defaults.line_channel_access_token,
            )
        ),
        line_channel_secret=_clean_secret(
            _env_first(
                ["LINE_CHANNEL_SECRET", "CHANNEL_SECRET"],
                defaults.line_channel_secret,
            )
        ),
        line_target_user_id=os.getenv(
            "LINE_TARGET_USER_ID", defaults.line_target_user_id
        ),
        rsi_alert_threshold=_float_env(
            "RSI_ALERT_THRESHOLD", defaults.rsi_alert_threshold
        ),
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_first(names, default=None):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _clean_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.startswith("***"):
        return None
    return cleaned
