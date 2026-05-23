"""
Auto-generates per-user rclone.conf from a GDrive OAuth token JSON.
Each user gets their own isolated config: data/users/<user_id>/rclone.conf
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
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    raw = raw.strip()
    try:
        token = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not {"access_token", "token_type", "refresh_token", "expiry"}.issubset(token.keys()):
        return None
    return token


def write_rclone_config(token: dict, user_id: int) -> None:
    path = config.user_rclone_config(user_id)
    remote = config.user_rclone_remote(user_id)
    with open(path, "w") as f:
        f.write(RCLONE_CONF_TEMPLATE.format(remote=remote, token_json=json.dumps(token)))
    logger.info(f"rclone config written: {path}")


def save_token_file(token: dict, user_id: int) -> None:
    path = config.user_token_file(user_id)
    with open(path, "w") as f:
        json.dump(token, f, indent=2)
    logger.info(f"Token saved: {path}")


def load_existing_token(user_id: int) -> Optional[dict]:
    path = config.user_token_file(user_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def is_rclone_configured(user_id: int) -> bool:
    path = config.user_rclone_config(user_id)
    return os.path.exists(path) and os.path.getsize(path) > 0


def apply_token(raw_token: str, user_id: int) -> tuple[bool, str]:
    token = validate_gdrive_token(raw_token)
    if token is None:
        return False, (
            "❌ <b>Invalid token format.</b>\n\n"
            "Please paste a valid GDrive OAuth JSON with keys:\n"
            "<code>access_token, token_type, refresh_token, expiry</code>"
        )
    try:
        write_rclone_config(token, user_id)
        save_token_file(token, user_id)
        return True, "✅ <b>GDrive Token Updated Successfully!</b>\nRemote is now active and ready."
    except OSError as e:
        return False, f"❌ Failed to write config: {e}"
