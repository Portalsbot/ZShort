import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API Credentials (from my.telegram.org)
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Channels & Admin IDs
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "0"))   # Storage/Dump Channel (-100...)
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))  # Log Channel (-100...)

# Branding & Social Links
OWNER_LINK = "https://t.me/reactivehcl"
OWNER_LABEL = "ʜᴄʟ"
DEV_LINK = "https://t.me/just_astha"
DEV_LABEL = "ᴀsᴛʜᴀ"

# Defaults
DEFAULT_IMAGE = os.environ.get("DEFAULT_IMAGE", "https://envs.sh/default.jpg")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "zshort_database.db")
