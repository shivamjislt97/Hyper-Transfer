"""
Auto-generates rclone.conf from a GDrive OAuth token JSON.
Validates the token and writes/updates the config file.
"""
import json
import os
import re
from typing import Optional

from loguru import logger

import config


RCLONE_CONF_TEMPLATE = """\
[{remote}]
type = drive
scope = drive
token = {token_json}
"""


def validate_gdrive_token(raw: str) -> Optional[dict]:
    """
    Validate that the raw string is a proper GDrive OAuth token JSON.
    Returns parsed dict on success, None on failure.
    """
    raw = raw.strip()
    # Strip code fences if user pasted with markdown
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    raw = raw.strip()

    try:
        token = json.loads(raw)
    except json.JSONDecodeError:
        return None

    required_keys = {"access_token", "token_type", "refresh_token", "expiry"}
    if not required_keys.issubset(token.keys()):
        return None

    return token


def write_rclone_config(token: dict) -> None:
    """Write rclone.conf with the provided token."""
    os.makedirs(os.path.dirname(config.RCLONE_CONFIG_PATH), exist_ok=True)
    token_json = json.dumps(token)
    conf_content = RCLONE_CONF_TEMPLATE.format(
        remote=config.RCLONE_REMOTE_NAME,
        token_json=token_json,
    )
    with open(config.RCLONE_CONFIG_PATH, "w") as f:
        f.write(conf_content)
    logger.info(f"rclone config written to: {config.RCLONE_CONFIG_PATH}")


def save_token_file(token: dict) -> None:
    """Persist the token JSON for future reference."""
    os.makedirs(os.path.dirname(config.TOKEN_FILE_PATH), exist_ok=True)
    with open(config.TOKEN_FILE_PATH, "w") as f:
        json.dump(token, f, indent=2)
    logger.info(f"Token saved to: {config.TOKEN_FILE_PATH}")


def load_existing_token() -> Optional[dict]:
    """Load the last saved token from disk, if present."""
    if not os.path.exists(config.TOKEN_FILE_PATH):
        return None
    try:
        with open(config.TOKEN_FILE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def is_rclone_configured() -> bool:
    """True if rclone.conf exists and is non-empty."""
    return os.path.exists(config.RCLONE_CONFIG_PATH) and os.path.getsize(config.RCLONE_CONFIG_PATH) > 0


def apply_token(raw_token: str) -> tuple[bool, str]:
    """
    Full pipeline: validate → write config → save token.
    Returns (success, message).
    """
    token = validate_gdrive_token(raw_token)
    if token is None:
        return False, (
            "❌ <b>Invalid token format.</b>\n\n"
            "Please paste a valid GDrive OAuth JSON with keys:\n"
            "<code>access_token, token_type, refresh_token, expiry</code>"
        )

    try:
        write_rclone_config(token)
        save_token_file(token)
        return True, "✅ <b>GDrive Token Updated Successfully!</b>\nRemote is now active and ready."
    except OSError as e:
        return False, f"❌ Failed to write config: {e}"
