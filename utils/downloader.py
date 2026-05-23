"""
megatools-based MEGA downloader with file-size-monitor progress tracking.
Progress is tracked by reading the growing file on disk — no output parsing.
Falls back to MegaBasterd when quota is exceeded.
"""
import asyncio
import os
import re

from aiogram import Bot
from loguru import logger

import config
from utils.size_monitor import monitor_download, run_and_signal


MEGA_LINK_RE = re.compile(
    r"https?://mega\.nz/(?:file|folder|#[!F])[^\s]+",
    re.IGNORECASE,
)

QUOTA_TOKENS = (
    "overquota", "quotaexceeded", "transferquota",
    "quota exceeded", "err: api", "-18",
)


def is_valid_mega_link(link: str) -> bool:
    return bool(MEGA_LINK_RE.match(link.strip()))


class DownloadResult:
    def __init__(self, success: bool, file_path: str = "", error: str = "") -> None:
        self.success = success
        self.file_path = file_path
        self.error = error


# ─── File info via megals ─────────────────────────────────────

async def get_mega_file_info(link: str) -> tuple[str, int]:
    """
    Returns (filename, size_bytes) using megals.
    Falls back to (placeholder, 10GB) if megals fails.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "megals", "-l", "--export", link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        for line in stdout.decode(errors="ignore").splitlines():
            parts = line.strip().split()
            # megals -l format: "FLAGS SIZE DATE TIME NAME"
            # The last field is the name (or path), size is typically 2nd field
            if len(parts) >= 5:
                try:
                    size = int(parts[1])
                    name = os.path.basename(parts[-1])
                    if name and size > 0:
                        return name, size
                except (ValueError, IndexError):
                    pass
    except Exception as e:
        logger.warning(f"megals failed: {e}")

    # Fallback
    placeholder = link.split("/")[-1].split("!")[0] or "mega_download"
    return placeholder, 10 * 1024 ** 3  # default 10 GB


# ─── Core downloader ──────────────────────────────────────────

async def download_with_megatools(
    link: str,
    dest_dir: str,
    filename: str,
    total_bytes: int,
    bot: Bot,
    chat_id: int,
    msg_id: int,
    transfer_ctx: dict,
) -> DownloadResult:
    """
    Download MEGA file using megatools.
    Progress via asyncio.gather(subprocess, file_size_monitor).
    Returns DownloadResult — error="QUOTA_EXCEEDED" triggers fallback.
    """
    os.makedirs(dest_dir, exist_ok=True)
    filepath   = os.path.join(dest_dir, filename)
    stop_event = transfer_ctx["stop_event"]

    logger.info(f"Starting megatools download: {link}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "megadl", "--path", dest_dir, link,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,  # capture stderr to detect quota error
        )
    except FileNotFoundError:
        return DownloadResult(False, error="megatools not installed. Run: sudo apt install megatools")

    transfer_ctx["proc"] = proc  # expose so cancel handler can kill it

    # Run subprocess + disk monitor in parallel
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

    # Check stderr for quota exceeded (proc is done at this point)
    stderr_bytes = await _read_stderr(proc)
    stderr_text  = stderr_bytes.decode("utf-8", errors="ignore")
    logger.debug(f"[megatools stderr] {stderr_text[:300]}")
    nospace = stderr_text.lower().replace(" ", "")
    if any(tok.replace(" ", "") in nospace for tok in QUOTA_TOKENS):
        return DownloadResult(False, error="QUOTA_EXCEEDED")

    if proc.returncode != 0:
        return DownloadResult(False, error=f"megatools exited {proc.returncode}: {stderr_text[-200:]}")

    # Resolve actual downloaded file (megadl uses real filename)
    actual = _newest_file(dest_dir)
    return DownloadResult(True, file_path=actual or filepath)


async def _read_stderr(proc) -> bytes:
    """Drain stderr after process finishes."""
    try:
        return await proc.stderr.read()
    except Exception:
        return b""


def _newest_file(directory: str) -> str:
    """Return path of most recently modified file in directory."""
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory)
                 if os.path.isfile(os.path.join(directory, f))]
        return max(files, key=os.path.getmtime) if files else ""
    except OSError:
        return ""


# ─── Retry wrapper ────────────────────────────────────────────

async def download_with_retry(
    link: str,
    dest_dir: str,
    filename: str,
    total_bytes: int,
    bot: Bot,
    chat_id: int,
    msg_id: int,
    transfer_ctx: dict,
) -> DownloadResult:
    """
    Tries megatools up to MAX_RETRIES times.
    On QUOTA_EXCEEDED returns immediately for MegaBasterd fallback.
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        if attempt > 1:
            if transfer_ctx.get("cancelled"):
                return DownloadResult(False, error="CANCELLED")
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=f"⚠️ *Retry {attempt}/{config.MAX_RETRIES}* — waiting {config.RETRY_DELAY}s...",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            await asyncio.sleep(config.RETRY_DELAY)

        # Reset stop_event for next attempt
        transfer_ctx["stop_event"] = asyncio.Event()
        result = await download_with_megatools(
            link, dest_dir, filename, total_bytes, bot, chat_id, msg_id, transfer_ctx
        )
        if result.success or result.error in ("QUOTA_EXCEEDED", "CANCELLED"):
            return result
        logger.warning(f"Download attempt {attempt} failed: {result.error}")

    return DownloadResult(False, error=f"Failed after {config.MAX_RETRIES} retries.")
