"""
File-size-based progress monitor.
Runs parallel to any subprocess via asyncio.gather().
Works with megatools, MegaBasterd, rclone — no output parsing needed.

transfer_ctx keys used here:
  stop_event    — asyncio.Event signalling download/upload done or cancelled
  cancel_keyboard — InlineKeyboardMarkup shown below every progress bar update
"""
import asyncio
import os
import re
import time

from aiogram import Bot
from utils.progress_bar import update_bar


async def monitor_download(
    filepath: str,
    total_bytes: int,
    filename: str,
    bot: Bot,
    chat_id: int,
    msg_id: int,
    transfer_ctx: dict,
) -> None:
    """
    Runs parallel to download subprocess.
    Every 3s: reads file size from disk → calculates % / speed / ETA → edits bar.
    Stops when transfer_ctx["stop_event"] is set.
    """
    stop_event     = transfer_ctx["stop_event"]
    cancel_keyboard = transfer_ctx.get("cancel_keyboard")

    prev_size = 0
    prev_time = time.monotonic()

    while not stop_event.is_set():
        await asyncio.sleep(3)

        try:
            current_size = os.path.getsize(filepath)
        except (FileNotFoundError, OSError):
            current_size = prev_size  # file not yet created — keep last value

        now     = time.monotonic()
        elapsed = now - prev_time
        speed   = (current_size - prev_size) / elapsed if elapsed > 0 else 0.0

        percent   = min(current_size / total_bytes * 100, 99.9) if total_bytes > 0 else 0.0
        remaining = max(total_bytes - current_size, 0)
        eta       = int(remaining / speed) if speed > 1 else 0

        await update_bar(
            bot=bot,
            chat_id=chat_id,
            message_id=msg_id,
            phase="download",
            percent=percent,
            transferred=current_size,
            total=total_bytes,
            speed=speed,
            eta=eta,
            filename=filename,
            reply_markup=cancel_keyboard,
        )

        prev_size = current_size
        prev_time = now


async def monitor_upload(
    local_filepath: str,
    filename: str,
    bot: Bot,
    chat_id: int,
    msg_id: int,
    transfer_ctx: dict,
) -> None:
    """
    Runs parallel to rclone upload subprocess.
    Parses rclone --log-file output every 3s for transferred bytes.
    Stops when transfer_ctx["stop_event"] is set.
    """
    stop_event      = transfer_ctx["stop_event"]
    cancel_keyboard  = transfer_ctx.get("cancel_keyboard")
    log_path         = transfer_ctx.get("log_path", local_filepath + ".rclone.log")
    total_bytes      = os.path.getsize(local_filepath) if os.path.exists(local_filepath) else 0
    prev_uploaded    = 0
    prev_time        = time.monotonic()

    while not stop_event.is_set():
        await asyncio.sleep(3)

        uploaded = _parse_rclone_log(log_path, total_bytes)

        now     = time.monotonic()
        elapsed = now - prev_time
        speed   = (uploaded - prev_uploaded) / elapsed if elapsed > 0 else 0.0

        percent   = min(uploaded / total_bytes * 100, 99.9) if total_bytes > 0 else 0.0
        remaining = max(total_bytes - uploaded, 0)
        eta       = int(remaining / speed) if speed > 1 else 0

        await update_bar(
            bot=bot,
            chat_id=chat_id,
            message_id=msg_id,
            phase="upload",
            percent=percent,
            transferred=uploaded,
            total=total_bytes,
            speed=speed,
            eta=eta,
            filename=filename,
            reply_markup=cancel_keyboard,
        )

        prev_uploaded = uploaded
        prev_time     = now


_RCLONE_SIZES = {
    "b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4,
    "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4,
}
_TRANSFERRED_RE = re.compile(
    r"Transferred:\s+([\d.]+)\s*(\w+)\s*/", re.IGNORECASE
)
_PCT_RE = re.compile(r",\s*(\d+)%")


def _parse_rclone_log(log_path: str, total: int) -> int:
    """
    Read rclone log file and return latest transferred bytes.
    Looks for the most recent 'Transferred:' line.
    """
    last_match = None
    try:
        with open(log_path, "r", errors="ignore") as f:
            for line in f:
                if "Transferred:" in line:
                    last_match = line
    except (FileNotFoundError, OSError):
        return 0

    if not last_match:
        return 0

    m = _TRANSFERRED_RE.search(last_match)
    if m:
        val  = float(m.group(1))
        unit = m.group(2).lower()
        return int(val * _RCLONE_SIZES.get(unit, 1))

    # Fallback: parse percentage
    p = _PCT_RE.search(last_match)
    if p and total:
        return int(total * int(p.group(1)) / 100)

    return 0


async def run_and_signal(process, stop_event: asyncio.Event) -> None:
    """Wait for subprocess to finish then signal the monitor to stop."""
    await process.wait()
    stop_event.set()
