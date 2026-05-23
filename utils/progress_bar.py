from aiogram import Bot

FILLED  = "█"
EMPTY   = "░"
BAR_LEN = 18


def build_bar(percent: float) -> str:
    filled = int(BAR_LEN * percent / 100)
    return FILLED * filled + EMPTY * (BAR_LEN - filled)


def human_size(b: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def human_eta(s: int) -> str:
    if s <= 0:
        return "--"
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    return f"{m}m {s}s" if m < 60 else f"{m // 60}h {m % 60}m"


async def update_bar(
    bot: Bot,
    chat_id: int,
    message_id: int,
    phase: str,           # "download" or "upload"
    percent: float,
    transferred: int,     # bytes
    total: int,           # bytes
    speed: float,         # bytes/sec
    eta: int,             # seconds
    filename: str,
    reply_markup=None,    # InlineKeyboardMarkup — cancel button lives here
) -> None:
    bar  = build_bar(percent)
    icon = "⬇️" if phase == "download" else "☁️"
    lbl  = "DOWNLOADING" if phase == "download" else "UPLOADING"
    dest = f"`{filename}`" if phase == "download" else f"`{filename}` → GDrive"
    spd_str = human_size(int(speed)) + "/s" if speed > 0 else "-- B/s"

    text = (
        f"{icon} *{lbl}...*\n"
        f"`{bar}` *{percent:.1f}%*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 `{human_size(transferred)}` / `{human_size(total)}`\n"
        f"⚡ `{spd_str}`\n"
        f"⏱️ ETA: `{human_eta(eta)}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📁 {dest}"
    )

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
    except Exception:
        pass  # Text unchanged or Telegram rate limit — silently skip
