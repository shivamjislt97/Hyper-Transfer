import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ALLOWED_USER_IDS: list[int] = [
    int(uid) for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") if uid.strip()
]

# ─── Paths ───────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WORKSPACE_PATH: str = os.getenv("WORKSPACE_PATH", "/teamspace/studios/this_studio/downloads")
RCLONE_CONFIG_PATH: str = os.path.join(DATA_DIR, "rclone.conf")
TOKEN_FILE_PATH: str = os.path.join(DATA_DIR, "token.json")
SESSION_FILE_PATH: str = os.path.join(DATA_DIR, "session.json")

# ─── GDrive / rclone ─────────────────────────────────────────
GDRIVE_FOLDER: str = os.getenv("GDRIVE_FOLDER", "mega_transfers")
RCLONE_REMOTE_NAME: str = os.getenv("RCLONE_REMOTE_NAME", "gdrive")

# ─── Storage ─────────────────────────────────────────────────
MAX_WORKSPACE_GB: float = float(os.getenv("MAX_WORKSPACE_GB", "198"))

# ─── MegaBasterd ─────────────────────────────────────────────
MEGABASTERD_JAR_PATH: str = os.getenv(
    "MEGABASTERD_JAR_PATH",
    "/opt/megabasterd/MegaBasterd.jar",
)

# ─── Progress bar ─────────────────────────────────────────────
PROGRESS_UPDATE_INTERVAL: int = int(os.getenv("PROGRESS_UPDATE_INTERVAL", "2"))
PROGRESS_BAR_LENGTH: int = 18

# ─── Retry ────────────────────────────────────────────────────
MAX_RETRIES: int = 3
RETRY_DELAY: int = 10  # seconds

# ─── Validation ───────────────────────────────────────────────
def validate_config() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set. Add it to your .env file.")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(WORKSPACE_PATH, exist_ok=True)


# ─── Per-user path helpers ────────────────────────────────────
def user_data_dir(user_id: int) -> str:
    """data/users/<user_id>/ — rclone.conf, token.json per user"""
    path = os.path.join(DATA_DIR, "users", str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def user_rclone_config(user_id: int) -> str:
    return os.path.join(user_data_dir(user_id), "rclone.conf")

def user_token_file(user_id: int) -> str:
    return os.path.join(user_data_dir(user_id), "token.json")

def user_workspace(user_id: int) -> str:
    """downloads/<user_id>/ — isolated download workspace per user"""
    path = os.path.join(WORKSPACE_PATH, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def user_rclone_remote(user_id: int) -> str:
    """Unique rclone remote name per user to avoid config conflicts"""
    return f"{RCLONE_REMOTE_NAME}_{user_id}"
