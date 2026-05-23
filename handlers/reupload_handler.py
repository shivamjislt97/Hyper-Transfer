"""
Reupload flow — upload a workspace file to GDrive without downloading.
Entry points:
  - menu:reupload_pick  — main menu button → file-as-button picker
  - ws:reupload:<index> — per-file button inside workspace manager
Both show files as tappable inline buttons — no typing needed.
"""
import asyncio
import os
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

from utils.uploader import upload_with_rclone
from utils.workspace_manager import list_workspace
from utils.progress_bar import human_size
from handlers.mega_handler import _active_transfers, cancel_keyboard

router = Router(name="reupload")


class ReuploadStates(StatesGroup):
    waiting_for_delete_choice = State()


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu:back")]]
    )


def _delete_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yes, Delete", callback_data="reupload:delete_yes"),
            InlineKeyboardButton(text="❌ Keep It",     callback_data="reupload:delete_no"),
        ]]
    )


def _file_pick_keyboard(entries) -> InlineKeyboardMarkup:
    def _icon(name: str) -> str:
        return "🎬" if name.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm")) else "📄"

    buttons = [
        [InlineKeyboardButton(
            text=f"{_icon(e.name)}  {e.name[:40]} — {human_size(e.size_bytes)}",
            callback_data=f"reupload:file:{e.index}",
        )]
        for e in entries
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_entries(user_id: int):
    return [e for e in list_workspace(user_id) if not e.name.endswith(".rclone.log")]


# ─── Main menu entry ──────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:reupload_pick")
async def cb_reupload_pick(callback: CallbackQuery, state: FSMContext) -> None:
    chat_id = callback.message.chat.id
    uid = callback.from_user.id
    if chat_id in _active_transfers:
        await callback.answer("⚠️ Transfer already in progress. Cancel it first.", show_alert=True)
        return

    from utils.rclone_setup import is_rclone_configured
    if not is_rclone_configured(uid):
        await callback.answer("❌ GDrive token not set. Please update it first.", show_alert=True)
        return

    entries = _get_entries(uid)
    if not entries:
        await callback.message.edit_text(
            "⚠️ <b>Workspace is empty.</b> No files to reupload.",
            reply_markup=_back_kb(), parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📂 <b>Select a file to reupload to GDrive:</b>",
        reply_markup=_file_pick_keyboard(entries), parse_mode="HTML",
    )
    await callback.answer()


# ─── File button tapped ───────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("reupload:file:"))
async def cb_reupload_file_pick(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    chat_id = callback.message.chat.id
    uid = callback.from_user.id
    if chat_id in _active_transfers:
        await callback.answer("⚠️ Transfer already in progress.", show_alert=True)
        return

    index = int(callback.data.split(":")[-1])
    entries = _get_entries(uid)
    match = next((e for e in entries if e.index == index), None)

    if not match or not os.path.exists(match.full_path):
        entries = _get_entries(uid)
        if entries:
            await callback.message.edit_text(
                "❌ <b>File no longer exists.</b> Select another:\n\n📂 <b>Select a file to reupload:</b>",
                reply_markup=_file_pick_keyboard(entries), parse_mode="HTML",
            )
        else:
            await callback.message.edit_text(
                "❌ <b>File no longer exists.</b> Workspace is now empty.",
                reply_markup=_back_kb(), parse_mode="HTML",
            )
        await callback.answer()
        return

    await callback.answer()
    await _start_reupload(callback.message, bot, state, match.full_path, match.name, match.size_bytes, uid)


# ─── Workspace manager per-file entry ────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("ws:reupload:"))
async def cb_ws_reupload(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    chat_id = callback.message.chat.id
    uid = callback.from_user.id
    if chat_id in _active_transfers:
        await callback.answer("⚠️ A transfer is already in progress.", show_alert=True)
        return

    index = int(callback.data.split(":")[-1])
    entries = _get_entries(uid)
    match = next((e for e in entries if e.index == index), None)
    if not match:
        await callback.answer("File not found.", show_alert=True)
        return

    await callback.answer()
    await _start_reupload(callback.message, bot, state, match.full_path, match.name, match.size_bytes, uid)


# ─── Shared upload runner ─────────────────────────────────────

async def _start_reupload(
    message: Message, bot: Bot, state: FSMContext,
    file_path: str, filename: str, file_size: float, user_id: int,
) -> None:
    from handlers.start_handler import main_menu_keyboard

    chat_id = message.chat.id

    status_msg = await message.answer(
        f"✅ <b>Starting reupload</b> — <code>{filename}</code> ({human_size(file_size)}) → GDrive",
        parse_mode="HTML",
    )
    msg_id = status_msg.message_id

    transfer_ctx: dict = {
        "stop_event":      asyncio.Event(),
        "proc":            None,
        "cancelled":       False,
        "file_path":       file_path,
        "log_path":        "",
        "phase":           "upload",
        "remote_path":     "",
        "cancel_keyboard": cancel_keyboard(),
    }
    _active_transfers[chat_id] = transfer_ctx

    result = await upload_with_rclone(file_path, filename, bot, chat_id, msg_id, transfer_ctx, user_id)

    _active_transfers.pop(chat_id, None)

    if transfer_ctx.get("cancelled"):
        await state.clear()
        return

    if not result.success:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"❌ <b>Upload Failed!</b>\n\n<code>{result.error}</code>",
            reply_markup=main_menu_keyboard(), parse_mode="HTML",
        )
        await state.clear()
        return

    await bot.edit_message_text(
        chat_id=chat_id, message_id=msg_id,
        text=(
            "🎉 <b>Upload Complete!</b>\n\n"
            f"✅ <code>{result.gdrive_path}</code>\n\n"
            "🗑️ <b>Delete local copy from workspace?</b>"
        ),
        reply_markup=_delete_choice_kb(), parse_mode="HTML",
    )
    await state.set_state(ReuploadStates.waiting_for_delete_choice)
    await state.update_data(file_path=file_path, filename=filename)


# ─── Post-upload delete prompt ────────────────────────────────

@router.callback_query(
    ReuploadStates.waiting_for_delete_choice,
    lambda c: c.data in ("reupload:delete_yes", "reupload:delete_no"),
)
async def cb_delete_choice(callback: CallbackQuery, state: FSMContext) -> None:
    from handlers.start_handler import main_menu_keyboard

    data = await state.get_data()
    file_path = data.get("file_path", "")
    filename  = data.get("filename", "")
    await state.clear()

    if callback.data == "reupload:delete_yes":
        try:
            Path(file_path).unlink(missing_ok=True)
            msg = f"✅ <b>Deleted:</b> <code>{filename}</code>"
        except Exception as e:
            msg = f"⚠️ Could not delete file: {e}"
    else:
        msg = f"📁 <b>Kept:</b> <code>{filename}</code> in workspace."

    await callback.message.edit_text(
        msg + "\n\nChoose your next action:",
        reply_markup=main_menu_keyboard(), parse_mode="HTML",
    )
    await callback.answer()
