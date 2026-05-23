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
    transfer_ctx: dict,  # required — carries stop_event, proc, cancel_keyboard, log_path
) -> UploadResult:
    """
    Upload file to GDrive using rclone.
    Progress via asyncio.gather(subprocess, monitor_upload).
    """
    if not os.path.exists(local_path):
        return UploadResult(False, error=f"Local path not found: {local_path}")

    remote_dest = f"{config.RCLONE_REMOTE_NAME}:{config.GDRIVE_FOLDER}"
    gdrive_path = f"/My Drive/{config.GDRIVE_FOLDER}/{filename}"
    log_file    = local_path + ".rclone.log"
    stop_event  = transfer_ctx["stop_event"]

    transfer_ctx["log_path"]      = log_file        # expose for cancel cleanup
    transfer_ctx["remote_path"]   = f"{config.RCLONE_REMOTE_NAME}:{config.GDRIVE_FOLDER}/{filename}"
    transfer_ctx["phase"]         = "upload"

    logger.info(f"Uploading '{local_path}' → {remote_dest}")

    cmd = [
        "rclone", "copy",
        "--config", config.RCLONE_CONFIG_PATH,
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
