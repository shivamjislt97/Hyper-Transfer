"""
Flow C — Workspace Manager.
List, delete specific, or clear all files in the download workspace.
"""
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from utils.workspace_manager import (
    clear_workspace,
    delete_by_index,
    format_workspace_listing,
    list_workspace,
)

router = Router(name="workspace")


def workspace_action_keyboard(entries, has_files: bool) -> InlineKeyboardMarkup:
    buttons = []
    for e in entries:
        buttons.append([
            InlineKeyboardButton(text=f"🔁 Reupload  {e.name[:28]}", callback_data=f"ws:reupload:{e.index}"),
            InlineKeyboardButton(text="🗑️ Delete",                   callback_data=f"ws:del:{e.index}"),
        ])
    if has_files:
        buttons.append([InlineKeyboardButton(text="💣 Clear All Workspace", callback_data="ws:clear_confirm")])
    buttons.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_clear_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, Clear All", callback_data="ws:clear_do"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="menu:workspace"),
            ]
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu:back")]]
    )


@router.callback_query(lambda c: c.data == "menu:workspace")
async def cb_workspace_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    entries = [e for e in list_workspace() if not e.name.endswith(".rclone.log")]
    text = format_workspace_listing(entries)
    await callback.message.edit_text(
        text, reply_markup=workspace_action_keyboard(entries, bool(entries)), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ws:del:"))
async def cb_ws_delete_file(callback: CallbackQuery) -> None:
    index = int(callback.data.split(":")[-1])
    success, msg = delete_by_index(index)
    entries = [e for e in list_workspace() if not e.name.endswith(".rclone.log")]
    text = format_workspace_listing(entries)
    await callback.message.edit_text(
        msg + "\n\n" + text,
        reply_markup=workspace_action_keyboard(entries, bool(entries)),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ws:clear_confirm")
async def cb_clear_confirm(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "⚠️ <b>Are you sure?</b>\n\nThis will delete <b>ALL files</b> in the workspace!",
        reply_markup=confirm_clear_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ws:clear_do")
async def cb_clear_do(callback: CallbackQuery) -> None:
    await callback.message.edit_text("⏳ Clearing workspace...", parse_mode="HTML")
    success, msg = clear_workspace()

    from handlers.start_handler import main_menu_keyboard
    await callback.message.edit_text(
        msg + "\n\nChoose your next action:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
