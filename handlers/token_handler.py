"""
Flow B — Change GDrive Token.
Guides the user through pasting their OAuth token and updates rclone config.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from utils.rclone_setup import apply_token

router = Router(name="token")


class TokenStates(StatesGroup):
    waiting_for_token = State()


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu:back")]]
    )


PASTE_PROMPT = (
    "🔑 <b>Change GDrive Token</b>\n\n"
    "Please paste your GDrive OAuth token JSON below 👇\n\n"
    "<i>Tip: Get it from the rclone authorization flow or your OAuth app credentials.</i>"
)


@router.callback_query(lambda c: c.data == "menu:token")
async def cb_token_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(PASTE_PROMPT, reply_markup=back_keyboard(), parse_mode="HTML")
    await state.set_state(TokenStates.waiting_for_token)
    await callback.answer()


@router.message(TokenStates.waiting_for_token)
async def handle_token_input(message: Message, state: FSMContext) -> None:
    raw = message.text or ""
    if not raw.strip():
        await message.answer("❌ Empty input. Please paste the JSON token.", parse_mode="HTML")
        return

    status_msg = await message.answer("⏳ Validating token...", parse_mode="HTML")
    success, msg = apply_token(raw)

    from handlers.start_handler import main_menu_keyboard
    await status_msg.edit_text(
        msg + "\n\n" + ("Choose your next action:" if success else ""),
        reply_markup=main_menu_keyboard() if success else back_keyboard(),
        parse_mode="HTML",
    )
    await state.clear()
