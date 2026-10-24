"""
Configuration settings for Attendix Telegram Bot.
Loads environment variables safely and provides encryption key management.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet

logger = logging.getLogger("attendix_bot")

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Load .env file from telegram_bot/.env or root .env
bot_env = BASE_DIR / ".env"
root_env = PROJECT_ROOT / ".env"

if bot_env.exists():
    load_dotenv(dotenv_path=bot_env)
elif root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Database path (SQLite)
DEFAULT_DB_PATH = str(BASE_DIR / "telegram_bot.db")
DATABASE_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH).strip()

# MITS IMS Base URL
IMS_BASE_URL = os.getenv("IMS_BASE_URL", "http://mitsims.in").strip().rstrip("/")

# Cache TTL in seconds (default: 5 minutes)
try:
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
except ValueError:
    CACHE_TTL_SECONDS = 300

# Concurrency limits for scraping
try:
    MAX_CONCURRENT_SCRAPES = int(os.getenv("MAX_CONCURRENT_SCRAPES", "2"))
except ValueError:
    MAX_CONCURRENT_SCRAPES = 2

# Encryption Key management
_ENV_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "").strip()


def get_encryption_key() -> bytes:
    """
    Retrieves or generates a persistent 32-byte Fernet key.
    If CREDENTIAL_ENCRYPTION_KEY is provided in the environment, validates and uses it.
    Otherwise, generates/reads from telegram_bot/.encryption_key for seamless persistence.
    """
    global _ENV_KEY
    if _ENV_KEY:
        try:
            # Validate Fernet key format
            Fernet(_ENV_KEY.encode())
            return _ENV_KEY.encode()
        except Exception as e:
            logger.warning(f"Invalid CREDENTIAL_ENCRYPTION_KEY in environment ({e}). Falling back to keyfile.")

    key_file = BASE_DIR / ".encryption_key"
    if key_file.exists():
        try:
            key_data = key_file.read_bytes().strip()
            Fernet(key_data)
            return key_data
        except Exception:
            pass

    # Generate a fresh secure Fernet key
    new_key = Fernet.generate_key()
    try:
        key_file.write_bytes(new_key)
        # Attempt to restrict file permissions on UNIX/Windows where applicable
        os.chmod(key_file, 0o600)
    except Exception as e:
        logger.warning(f"Could not persist .encryption_key to disk: {e}")

    return new_key


def get_cipher() -> Fernet:
    """Returns a Fernet cipher instance initialized with the active encryption key."""
    return Fernet(get_encryption_key())
