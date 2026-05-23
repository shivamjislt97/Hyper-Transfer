"""
Flow A — MEGA Link Transfer.
Download → (quota fallback) → Upload → Completion.
Progress bar via bot.edit_message_text on a single pinned status message.
"""
import asyncio
import os
import time
from pathlib import Path

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from loguru import logger

import config
from utils.downloader import DownloadResult, download_with_retry, get_mega_file_info, is_valid_mega_link
from utils.progress_bar import human_size
from utils.rclone_setup import is_rclone_configured
from utils.uploader import upload_with_rclone
from utils.workspace_manager import get_workspace_free_bytes
from services.megabasterd_runner import download_with_megabasterd

router = Router(name="mega")

# Per-chat active transfer state — keyed by chat_id
_active_transfers: dict[int, dict] = {}


class MegaStates(StatesGroup):
    waiting_for_link = State()
    transferring = State()


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu:back")]]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel Transfer", callback_data="transfer:cancel")]]
    )


# ─── Cancel handler ───────────────────────────────────────────

@router.callback_query(lambda c: c.data == "transfer:cancel")
async def cb_cancel_transfer(callback: CallbackQuery, state: FSMContext) -> None:
    from handlers.start_handler import main_menu_keyboard

    chat_id = callback.message.chat.id
    ctx = _active_transfers.get(chat_id)

    if not ctx:
        await callback.answer("No active transfer.", show_alert=False)
        return

    ctx["cancelled"] = True
    ctx["stop_event"].set()

    # Kill the active subprocess
    proc = ctx.get("proc")
    if proc and proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass

    # Cleanup partial file
    file_path = ctx.get("file_path", "")
    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Cleanup rclone log
    log_path = ctx.get("log_path", "")
    if log_path:
        try:
            Path(log_path).unlink(missing_ok=True)
        except Exception:
            pass

    _active_transfers.pop(chat_id, None)
    await state.clear()

    try:
        await callback.message.edit_text(
            "🚫 *Transfer Cancelled.*\n\nPartial files have been removed.",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await callback.answer()


# ─── Entry point ─────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:mega")
async def cb_mega_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_rclone_configured():
        await callback.message.edit_text(
            "⚠️ *GDrive is not configured yet!*\n\n"
            "Please set your GDrive token first via 🔑 *Change GDrive Token*.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔑 Set GDrive Token", callback_data="menu:token")],
                    [InlineKeyboardButton(text="🔙 Back", callback_data="menu:back")],
                ]
            ),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📁 *Share Mega Link*\n\n"
        "Please paste your MEGA link below 👇\n\n"
        "_Supported: mega.nz/file/... and mega.nz/folder/..._",
        reply_markup=back_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(MegaStates.waiting_for_link)
    await callback.answer()


# ─── Link received ────────────────────────────────────────────

@router.message(MegaStates.waiting_for_link)
async def handle_mega_link(message: Message, bot: Bot, state: FSMContext) -> None:
    link = (message.text or "").strip()

    if not is_valid_mega_link(link):
        await message.answer(
            "❌ *Invalid link format.*\n\n"
            "Please paste a valid MEGA link:\n`https://mega.nz/file/...`",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return

    await state.set_state(MegaStates.transferring)
    await _run_transfer(message, bot, state, link)


# ─── Transfer orchestrator ────────────────────────────────────

async def _run_transfer(message: Message, bot: Bot, state: FSMContext, link: str) -> None:
    from handlers.start_handler import main_menu_keyboard

    dest_dir = config.WORKSPACE_PATH
    chat_id  = message.chat.id
    start_time = time.time()

    # ── Pre-flight space check ─────────────────────────────────
    free = get_workspace_free_bytes()
    if free < 1 * 1024**3:
        await message.answer(
            f"⚠️ *Workspace low on space!*\nOnly `{human_size(free)}` left.\n"
            "Please clear files before downloading.",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        await state.clear()
        return

    # ── Get file info (name + size) before starting ──────────
    status_msg = await message.answer(
        "⏳ *Fetching file info...*", parse_mode="Markdown"
    )
    msg_id = status_msg.message_id

    filename, total_bytes = await get_mega_file_info(link)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=(
                "⬇️ *DOWNLOADING...*\n"
                "`░░░░░░░░░░░░░░░░░░` *0.0%*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📦 `0 B / {human_size(total_bytes)}`\n"
                "⚡ `-- MB/s`\n"
                "⏱️ ETA: `--`\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📁 `{filename}`"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    # ── Build shared transfer context ─────────────────────────
    transfer_ctx: dict = {
        "stop_event":      asyncio.Event(),
        "proc":            None,
        "cancelled":       False,
        "file_path":       os.path.join(dest_dir, filename),
        "log_path":        "",
        "phase":           "download",
        "remote_path":     "",
        "cancel_keyboard": cancel_keyboard(),
    }
    _active_transfers[chat_id] = transfer_ctx

    # ── Download via megatools ─────────────────────────────────
    result: DownloadResult = await download_with_retry(
        link, dest_dir, filename, total_bytes, bot, chat_id, msg_id, transfer_ctx
    )

    if transfer_ctx.get("cancelled"):
        _active_transfers.pop(chat_id, None)
        await state.clear()
        return

    # ── Quota exceeded → MegaBasterd fallback ─────────────────
    if not result.success and result.error == "QUOTA_EXCEEDED":
        logger.warning("MEGA quota exceeded — switching to MegaBasterd")
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=(
                    "⚠️ *MEGA Quota Exceeded!*\n\n"
                    "🔄 Switching to MegaBasterd engine...\n"
                    "`Restarting download — please wait`"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass
        await asyncio.sleep(2)

        # Reset stop_event for MegaBasterd phase
        transfer_ctx["stop_event"] = asyncio.Event()
        mb_result = await download_with_megabasterd(
            link, dest_dir, filename, total_bytes, bot, chat_id, msg_id, transfer_ctx
        )

        if transfer_ctx.get("cancelled"):
            _active_transfers.pop(chat_id, None)
            await state.clear()
            return

        if not mb_result.success:
            _active_transfers.pop(chat_id, None)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=(
                    "❌ *Both engines failed.*\n\n"
                    f"`{mb_result.error}`\n\nPlease try again later."
                ),
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown",
            )
            await state.clear()
            return
        file_path = mb_result.file_path

    elif not result.success:
        _active_transfers.pop(chat_id, None)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"❌ *Download Failed!*\n\n`{result.error}`",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        await state.clear()
        return
    else:
        file_path = result.file_path

    filename  = os.path.basename(file_path.rstrip("/"))
    file_size = _get_size(file_path)

    # ── Between phases announcement ────────────────────────────
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=(
                "✅ *Download Complete!*\n"
                f"📦 `{filename}` — `{human_size(file_size)}`\n\n"
                "☁️ *UPLOADING...*\n"
                "`░░░░░░░░░░░░░░░░░░` *0.0%*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📤 `0 B / Calculating...`\n"
                "⚡ `-- MB/s`\n"
                "⏱️ ETA: `--`\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📁 `{filename}` → GDrive"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass
    await asyncio.sleep(1)

    # ── Reset stop_event for upload phase (download already set it) ────
    transfer_ctx["stop_event"] = asyncio.Event()

    # ── Upload via rclone ──────────────────────────────────────
    upload_result = await upload_with_rclone(
        file_path, filename, bot, chat_id, msg_id, transfer_ctx
    )

    if not upload_result.success:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"❌ *Upload Failed!*\n\n`{upload_result.error}`",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        await state.clear()
        return

    # ── Delete local file after successful upload ──────────────
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        pass

    # ── Completion ─────────────────────────────────────────────
    elapsed_str = _format_elapsed(time.time() - start_time)
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg_id,
        text=(
            "🎉 *Transfer Complete!*\n\n"
            "✅ File saved to GDrive\n"
            f"`{upload_result.gdrive_path}`\n\n"
            f"📦 Size: `{human_size(file_size)}`\n"
            f"⏱️ Total Time: `{elapsed_str}`\n\n"
            "🙏 *Thank you for using our service!*"
        ),
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
    await state.clear()


# ─── Helpers ──────────────────────────────────────────────────

def _get_size(path: str) -> float:
    if os.path.isfile(path):
        return float(os.path.getsize(path))
    total = 0.0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _format_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
