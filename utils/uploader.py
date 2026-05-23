"""
rclone-based Google Drive uploader with file-size-monitor progress tracking.
Progress via asyncio.gather(subprocess, monitor_upload).
rclone writes stats to --log-file; monitor parses it every 3 seconds.
"""
import asyncio
import os

from aiogram import Bot
from loguru import logger

import config
from utils.size_monitor import monitor_upload, run_and_signal


class UploadResult:
    def __init__(self, success: bool, gdrive_path: str = "", error: str = "") -> None:
        self.success = success
        self.gdrive_path = gdrive_path
        self.error = error


async def upload_with_rclone(
    local_path: str,
    filename: str,
    bot: Bot,
    chat_id: int,
    msg_id: int,
    transfer_ctx: dict,
    user_id: int,
) -> UploadResult:
    """
    Upload file to GDrive using rclone with per-user config.
    """
    if not os.path.exists(local_path):
        return UploadResult(False, error=f"Local path not found: {local_path}")

    rclone_config = config.user_rclone_config(user_id)
    remote_name   = config.user_rclone_remote(user_id)
    remote_dest   = f"{remote_name}:{config.GDRIVE_FOLDER}"
    gdrive_path   = f"/My Drive/{config.GDRIVE_FOLDER}/{filename}"
    log_file      = local_path + ".rclone.log"
    stop_event    = transfer_ctx["stop_event"]

    transfer_ctx["log_path"]    = log_file
    transfer_ctx["remote_path"] = f"{remote_name}:{config.GDRIVE_FOLDER}/{filename}"
    transfer_ctx["phase"]       = "upload"

    logger.info(f"Uploading '{local_path}' → {remote_dest} (user {user_id})")

    cmd = [
        "rclone", "copy",
        "--config", rclone_config,
        "--log-file", log_file,
        "--log-level", "INFO",
        "--stats", "3s",
        "--stats-one-line",
        local_path,
        remote_dest,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return UploadResult(False, error="rclone not installed. Run: sudo apt install rclone")

    transfer_ctx["proc"] = proc  # expose so cancel handler can kill it

    # Run subprocess + log monitor in parallel
    await asyncio.gather(
        run_and_signal(proc, stop_event),
        monitor_upload(
            local_filepath=local_path,
            filename=filename,
            bot=bot,
            chat_id=chat_id,
            msg_id=msg_id,
            transfer_ctx=transfer_ctx,
        ),
    )

    # Cleanup log file
    try:
        os.remove(log_file)
    except FileNotFoundError:
        pass

    if proc.returncode != 0:
        return UploadResult(False, error=f"rclone exited with code {proc.returncode}")

    return UploadResult(True, gdrive_path=gdrive_path)
