import os
import secrets
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    admin_username: str
    admin_password: str
    secret_key: str
    binance_api_key: str
    binance_api_secret: str
    binance_testnet_api_key: str
    binance_testnet_api_secret: str
    allow_live_trading: bool
    database_path: str
    resume_bots_on_startup: bool
    session_https_only: bool


def load_settings() -> Settings:
    secret_key = os.getenv("SECRET_KEY") or ""
    if not secret_key:
        # Kalıcı değil: sunucu her yeniden başladığında oturumlar düşer.
        secret_key = secrets.token_hex(32)
    return Settings(
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        secret_key=secret_key,
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        binance_testnet_api_key=os.getenv("BINANCE_TESTNET_API_KEY", ""),
        binance_testnet_api_secret=os.getenv("BINANCE_TESTNET_API_SECRET", ""),
        allow_live_trading=_bool("ALLOW_LIVE_TRADING", False),
        database_path=os.getenv("DATABASE_PATH", "tradebot.db"),
        resume_bots_on_startup=_bool("RESUME_BOTS_ON_STARTUP", True),
        session_https_only=_bool("SESSION_HTTPS_ONLY", False),
    )
