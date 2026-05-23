"""
MegaBasterd fallback downloader.
Runs MegaBasterd.jar headlessly; progress via file-size monitor.
"""
import asyncio
import os

from aiogram import Bot
from loguru import logger

import config
from utils.size_monitor import monitor_download, run_and_signal


class MegaBasterdResult:
    def __init__(self, success: bool, file_path: str = "", error: str = "") -> None:
        self.success = success
        self.file_path = file_path
        self.error = error


async def download_with_megabasterd(
    link: str,
    dest_dir: str,
    filename: str,
    total_bytes: int,
    bot: Bot,
    chat_id: int,
    msg_id: int,
    transfer_ctx: dict,
) -> MegaBasterdResult:
    """
    Download a MEGA link using MegaBasterd CLI mode.
    Progress via asyncio.gather(subprocess, file_size_monitor).
    """
    jar = config.MEGABASTERD_JAR_PATH
    if not os.path.exists(jar):
        return MegaBasterdResult(
            False,
            error=f"MegaBasterd JAR not found at: {jar}\nSet MEGABASTERD_JAR_PATH in .env",
        )

    os.makedirs(dest_dir, exist_ok=True)
    filepath   = os.path.join(dest_dir, filename)
    stop_event = transfer_ctx["stop_event"]
    logger.info(f"Starting MegaBasterd download: {link}")

    cmd = [
        "java", "-jar", jar,
        "--download", link,
        "--output-dir", dest_dir,
        "--no-gui",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return MegaBasterdResult(
            False, error="Java not found. Install: sudo apt install default-jre"
        )

    transfer_ctx["proc"] = proc  # expose so cancel handler can kill it

    await asyncio.gather(
        run_and_signal(proc, stop_event),
        monitor_download(
            filepath=filepath,
            total_bytes=total_bytes,
            filename=filename,
            bot=bot,
            chat_id=chat_id,
            msg_id=msg_id,
            transfer_ctx=transfer_ctx,
        ),
    )

    if proc.returncode != 0:
        return MegaBasterdResult(False, error=f"MegaBasterd exited with code {proc.returncode}")

    # Find the downloaded file
    try:
        files = [os.path.join(dest_dir, f) for f in os.listdir(dest_dir)
                 if os.path.isfile(os.path.join(dest_dir, f))]
        file_path = max(files, key=os.path.getmtime) if files else filepath
    except OSError:
        file_path = filepath

    return MegaBasterdResult(True, file_path=file_path)
