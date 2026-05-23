"""
/start command handler — shows main menu with inline buttons.
"""
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config

router = Router(name="start")


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Share Mega Link", callback_data="menu:mega"),
                InlineKeyboardButton(text="🔑 Change GDrive Token", callback_data="menu:token"),
            ],
            [
                InlineKeyboardButton(text="🗂️ Manage Workspace", callback_data="menu:workspace"),
                InlineKeyboardButton(text="🔁 Reupload to GDrive", callback_data="menu:reupload_pick"),
            ],
        ]
    )


WELCOME_TEXT = (
    "👋 <b>Welcome to Mega → GDrive Bot!</b>\n\n"
    "I can download files from MEGA and upload them directly to your Google Drive.\n\n"
    "Please choose an action below:"
)


def _is_allowed(user_id: int) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    return user_id in config.ALLOWED_USER_IDS


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not _is_allowed(message.from_user.id):
        await message.answer("⛔ You are not authorized to use this bot.")
        return
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "menu:back")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        WELCOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode="HTML"
    )
    await callback.answer()
